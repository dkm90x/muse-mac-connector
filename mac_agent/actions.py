"""Allowlisted, confirmation-aware actions Muse can request on macOS."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _within_roots(path: str, roots: list[str]) -> bool:
    resolved = os.path.realpath(os.path.expanduser(path))
    for root in roots:
        allowed = os.path.realpath(os.path.expanduser(root))
        if resolved == allowed or resolved.startswith(allowed + os.sep):
            return True
    return False


def _path_allowed(path: str, roots: list[str] | None) -> bool:
    # None explicitly denotes Full Mode; an empty Restricted Mode root list denies all.
    return roots is None or _within_roots(path, roots)


def _confirm_action(action: str, params: dict) -> bool:
    summary = json.dumps(params, ensure_ascii=False, default=str)
    if len(summary) > 1200:
        summary = summary[:1197] + "..."
    message = f"Muse wants to run: {action}\n\n{summary}"
    script = (
        "on run argv\n"
        "display dialog (item 1 of argv) with title \"Muse Mac Connector\" "
        "buttons {\"Deny\", \"Allow\"} default button \"Deny\" cancel button \"Deny\"\n"
        "end run"
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script, message],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_shortcuts(name: str, input_text: str = "") -> dict:
    if not name:
        return {"ok": False, "error": "shortcut name is required"}
    try:
        result = subprocess.run(
            ["shortcuts", "run", name, *(["-i", input_text] if input_text else [])],
            capture_output=True, text=True, timeout=120,
        )
        return {"ok": result.returncode == 0, "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:], "returncode": result.returncode}
    except FileNotFoundError:
        return {"ok": False, "error": "shortcuts CLI not available"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "shortcut timed out after 120s"}


def files_move(src: str, dst: str, allowed_roots: list[str] | None) -> dict:
    if not _path_allowed(src, allowed_roots) or not _path_allowed(dst, allowed_roots):
        return {"ok": False, "error": "path outside allowed roots"}
    try:
        Path(os.path.dirname(os.path.expanduser(dst))).mkdir(parents=True, exist_ok=True)
        shutil.move(os.path.expanduser(src), os.path.expanduser(dst))
        return {"ok": True, "src": src, "dst": dst}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def files_copy(src: str, dst: str, allowed_roots: list[str] | None) -> dict:
    if not _path_allowed(src, allowed_roots) or not _path_allowed(dst, allowed_roots):
        return {"ok": False, "error": "path outside allowed roots"}
    try:
        Path(os.path.dirname(os.path.expanduser(dst))).mkdir(parents=True, exist_ok=True)
        shutil.copy2(os.path.expanduser(src), os.path.expanduser(dst))
        return {"ok": True, "src": src, "dst": dst}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def settings_defaults(domain: str, key: str, value: str) -> dict:
    if not domain or not key:
        return {"ok": False, "error": "domain and key are required"}
    try:
        result = subprocess.run(
            ["defaults", "write", domain, key, "-string", str(value)],
            capture_output=True, text=True, timeout=15,
        )
        return {"ok": result.returncode == 0, "stderr": result.stderr[-4000:]}
    except FileNotFoundError:
        return {"ok": False, "error": "defaults CLI not available"}


def system_open_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"ok": False, "error": "only valid http(s) URLs are allowed"}
    try:
        subprocess.run(["open", url], timeout=10, check=False)
        return {"ok": True, "url": url}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def shell_script(name: str, scripts_dir: str) -> dict:
    if not name or "/" in name or name.startswith("."):
        return {"ok": False, "error": "invalid script name"}
    script = Path(scripts_dir) / name
    try:
        resolved = script.resolve()
        root = Path(scripts_dir).resolve()
    except OSError:
        return {"ok": False, "error": "script not found"}
    if resolved.parent != root or not resolved.is_file() or not os.access(resolved, os.X_OK):
        return {"ok": False, "error": "script not found or not executable"}
    try:
        result = subprocess.run([str(resolved)], capture_output=True, text=True, timeout=300)
        return {"ok": result.returncode == 0, "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-4000:], "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "script timed out after 300s"}


def execute(action: str, params: dict, cfg: dict) -> dict:
    """Execute one configured action, asking the Mac user first when required."""
    from .capabilities import available_actions, ACCESS_REQUEST
    from .config import CONFIG_LOCK, FULL_MODE_CONSENT, apply_full_mode, FULL_OPERATOR_CONFIRM_ACTIONS
    from .operator_actions import command_requires_confirmation

    if not isinstance(params, dict):
        return {"ok": False, "status": "denied", "error": "params must be an object"}
    if action == ACCESS_REQUEST:
        # This action is always discoverable, and no remote parameter can waive consent.
        with CONFIG_LOCK:
            if cfg.get("mode") == "full":
                return {"ok": True, "mode": "full", "restart_required": False, "already_enabled": True}
        if not _confirm_action(action, {"request": FULL_MODE_CONSENT}):
            return {"ok": False, "status": "denied", "error": "user denied Full Computer Mode"}
        try:
            apply_full_mode(cfg)
        except OSError as exc:
            return {"ok": False, "error": f"could not save Full Computer Mode: {exc}"}
        return {"ok": True, "mode": "full", "restart_required": False}

    with CONFIG_LOCK:
        cfg = dict(cfg)  # Each action sees one consistent authority snapshot.
    if action not in available_actions(cfg):
        return {"ok": False, "status": "denied", "error": "action is not allowlisted"}
    full = cfg.get("mode") == "full"
    risky = full and (
        action in FULL_OPERATOR_CONFIRM_ACTIONS or
        (action in {"shell.exec", "process.start"} and
         command_requires_confirmation(params.get("command", "")))
    )
    if (risky or action in cfg.get("confirm_actions", [])) and not _confirm_action(action, params):
        return {"ok": False, "status": "denied", "error": "user denied the action"}

    try:
        if action == "shortcuts.run":
            return run_shortcuts(params.get("name", ""), params.get("input", ""))
        if action == "files.move":
            return files_move(params.get("src", ""), params.get("dst", ""), None if full else cfg["allowed_roots"])
        if action == "files.copy":
            return files_copy(params.get("src", ""), params.get("dst", ""), None if full else cfg["allowed_roots"])
        if action == "settings.defaults":
            return settings_defaults(params.get("domain", ""), params.get("key", ""), params.get("value", ""))
        if action == "system.open_url":
            return system_open_url(params.get("url", ""))
        if action == "shell.script":
            return shell_script(params.get("name", ""), cfg["scripts_dir"])

        # Import lazily to keep the base agent lightweight and avoid circular imports.
        from .operator_actions import execute_operator
        operator_result = execute_operator(action, params, cfg)
        if operator_result is not None:
            return operator_result

        from .ui_actions import execute_ui
        ui_result = execute_ui(action, params, cfg)
        if ui_result is not None:
            return ui_result
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"action failed: {exc}"}
    return {"ok": False, "error": "unknown action"}
