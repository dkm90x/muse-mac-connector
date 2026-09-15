"""Mac Agent entrypoint for the Muse Mac Connector."""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

from . import __version__
from .config import load_config, write_example_config
from .http_api import serve as serve_http


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mac-agent",
        description="Authenticated local macOS capability service for Muse.",
    )
    parser.add_argument("--config", default=None, help="Path to config.yaml")
    parser.add_argument("--init", action="store_true", help="Create example config and exit")
    parser.add_argument("--http", action="store_true", help="Serve the local HTTP API")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    cfg = load_config(args.config)
    base = Path(cfg["base_dir"])
    base.mkdir(parents=True, exist_ok=True)
    Path(cfg["scripts_dir"]).mkdir(parents=True, exist_ok=True)

    if args.init:
        write_example_config(str(base / "config.yaml"))
        print(f"Initialized {base}")
        return 0
    if not args.http:
        print("Nothing to do: start with --http", file=sys.stderr)
        return 2
    if not os.environ.get("MAC_AGENT_TOKEN"):
        print("MAC_AGENT_TOKEN is required", file=sys.stderr)
        return 2

    stop = threading.Event()

    def _signal_handler(signum, frame):
        stop.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    serve_http(cfg)
    print(f"mac-agent v{__version__} serving on 127.0.0.1:8899", flush=True)
    try:
        while not stop.is_set():
            time.sleep(1)
    finally:
        print("mac-agent stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
