"""Mac Agent entrypoint and local capability CLI for Muse Mac Connector."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path

from . import __version__
from .capabilities import FULL_OPERATOR_PACKS, describe
from .config import enable_packs, load_config, write_example_config
from .http_api import serve as serve_http


def _print_capabilities(cfg: dict) -> None:
    print(f"Mode: {cfg.get('mode', 'restricted')}")
    if cfg.get("mode") == "full":
        print("Filesystem: user_accessible; commands: general; OS permissions and high-risk approvals apply.")
    else:
        print(f"Working roots: {', '.join(cfg.get('allowed_roots', []))}")
    print("Access request: access.enable_full (explicit local approval)")
    print()
    for name, item in describe(cfg).items():
        status = "ENABLED" if item["enabled"] else "disabled"
        print(f"{name:<12} {status:<8} {item['description']}")


def _doctor(cfg: dict) -> int:
    checks = {
        "python": sys.executable,
        "open": shutil.which("open"),
        "pbcopy": shutil.which("pbcopy"),
        "pbpaste": shutil.which("pbpaste"),
        "shortcuts": shutil.which("shortcuts"),
        "screencapture": shutil.which("screencapture") or ("/usr/sbin/screencapture" if Path("/usr/sbin/screencapture").exists() else None),
        "osascript": shutil.which("osascript") or ("/usr/bin/osascript" if Path("/usr/bin/osascript").exists() else None),
        "git": shutil.which("git"),
        "node": shutil.which("node"),
        "npm": shutil.which("npm"),
    }
    print(f"Muse Mac Connector {__version__}")
    print(f"Mode: {cfg.get('mode', 'restricted')}")
    for name, value in checks.items():
        print(f"{name:<14} {'READY' if value else 'missing'}{f'  {value}' if value else ''}")
    if sys.platform == "darwin":
        try:
            from .ui_actions import accessibility_status
            access = accessibility_status()
            print(f"accessibility  {'READY' if access.get('enabled') else 'needs approval'}")
        except Exception as exc:  # noqa: BLE001
            print(f"accessibility  check failed  {exc}")
    for root in ([] if cfg.get("mode") == "full" else cfg.get("allowed_roots", [])):
        print(f"root           {'READY' if Path(root).exists() else 'missing'}  {root}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="muse-mac",
        description="Authenticated macOS capability service and capability manager for Muse.",
    )
    parser.add_argument("command", nargs="?", choices=["capabilities", "enable", "doctor"])
    parser.add_argument("targets", nargs="*", help="Capability packs for 'enable', or 'all'")
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--init", action="store_true", help="Create example config and exit")
    parser.add_argument("--http", action="store_true", help="Serve the local HTTP API")
    parser.add_argument("--port", type=int, default=8899, help="Local HTTP port")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--self-test", action="store_true", help="Run a local HTTP smoke test and exit")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    cfg = load_config(args.config)
    base = Path(cfg["base_dir"])
    base.mkdir(parents=True, exist_ok=True)
    Path(cfg["scripts_dir"]).mkdir(parents=True, exist_ok=True)

    if args.command == "capabilities":
        _print_capabilities(cfg)
        return 0
    if args.command == "doctor":
        return _doctor(cfg)
    if args.command == "enable":
        targets = args.targets or []
        if not targets:
            print("Choose one or more capability packs, or: muse-mac enable all", file=sys.stderr)
            print("Available: " + ", ".join(FULL_OPERATOR_PACKS), file=sys.stderr)
            return 2
        if "all" in targets:
            from .actions import _confirm_action
            from .config import FULL_MODE_CONSENT
            if not _confirm_action("access.enable_full", {"request": FULL_MODE_CONSENT}):
                print("Full Computer Mode was not enabled.", file=sys.stderr)
                return 1
        try:
            cfg = enable_packs(targets, args.config)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print("Enabled Full Computer Mode." if cfg.get("mode") == "full" else "Capabilities enabled.")
        _print_capabilities(cfg)
        print("\nSaved. If a separate helper is already running, reopen the app to reload manual CLI configuration. Muse/menu Full Mode requests apply live without restart.")
        return 0

    if args.init:
        write_example_config(str(base / "config.yaml"))
        print(f"Initialized {base}")
        return 0
    if args.self_test:
        token = "self-test-" + secrets.token_hex(16)
        os.environ["MAC_AGENT_TOKEN"] = token
        server = serve_http(cfg, port=args.port)
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{args.port}/health",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read())
            ok = response.status == 200 and payload.get("ok") is True
            print("self-test: ok" if ok else "self-test: failed", flush=True)
            return 0 if ok else 1
        finally:
            server.shutdown()
            server.server_close()
    if not args.http:
        print("Nothing to do. Try 'muse-mac capabilities', 'muse-mac enable all', or start with --http.", file=sys.stderr)
        return 2
    if not os.environ.get("MAC_AGENT_TOKEN"):
        print("MAC_AGENT_TOKEN is required", file=sys.stderr)
        return 2

    stop = threading.Event()

    def _signal_handler(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    server = serve_http(cfg, port=args.port)
    print(f"mac-agent v{__version__} serving on 127.0.0.1:{args.port}", flush=True)
    try:
        while not stop.is_set():
            time.sleep(1)
    finally:
        server.shutdown()
        server.server_close()
        print("mac-agent stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
