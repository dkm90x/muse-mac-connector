"""Visual and Accessibility-based computer operator actions for macOS."""
from __future__ import annotations

import base64
import subprocess
import time
import uuid
from pathlib import Path

MAX_SCREEN_BYTES = 3 * 1024 * 1024
MAX_TYPED_CHARS = 20_000
KEY_CODES = {
    "return": 36, "tab": 48, "space": 49, "delete": 51, "escape": 53,
    "home": 115, "pageup": 116, "end": 119, "pagedown": 121,
    "left": 123, "right": 124, "down": 125, "up": 126,
}
MODIFIERS = {
    "command": "command down",
    "shift": "shift down",
    "option": "option down",
    "control": "control down",
}


def _osascript(script: str, *args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["/usr/bin/osascript", "-e", script, *[str(arg) for arg in args]],
        capture_output=True, text=True, timeout=timeout,
    )


def accessibility_status() -> dict:
    try:
        result = _osascript('tell application "System Events" to get UI elements enabled')
        enabled = result.returncode == 0 and result.stdout.strip().lower() == "true"
        return {"ok": True, "enabled": enabled, "stderr": result.stderr[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "enabled": False, "error": str(exc)}


def screen_capture(base_dir: str, display=None, include_base64: bool = True) -> dict:
    try:
        screenshots = Path(base_dir) / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        path = screenshots / f"screen-{int(time.time())}-{uuid.uuid4().hex[:6]}.jpg"
        command = ["/usr/sbin/screencapture", "-x", "-t", "jpg"]
        if display is not None:
            display_num = int(display)
            if display_num < 1 or display_num > 16:
                return {"ok": False, "error": "display must be between 1 and 16"}
            command.extend(["-D", str(display_num)])
        command.append(str(path))
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        if result.returncode != 0 or not path.is_file():
            return {"ok": False, "error": result.stderr.strip() or "screen capture failed"}
        size = path.stat().st_size
        payload = {"ok": True, "path": str(path), "mime_type": "image/jpeg", "bytes": size}
        if include_base64:
            if size <= MAX_SCREEN_BYTES:
                payload["image_base64"] = base64.b64encode(path.read_bytes()).decode("ascii")
            else:
                payload["base64_omitted"] = f"capture exceeds {MAX_SCREEN_BYTES} bytes"
        old = sorted(screenshots.glob("screen-*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)[20:]
        for item in old:
            try:
                item.unlink()
            except OSError:
                pass
        return payload
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def ui_frontmost() -> dict:
    script = '''
on run argv
    tell application "System Events"
        set p to first application process whose frontmost is true
        set appName to name of p as text
        set windowName to ""
        try
            set windowName to name of front window of p as text
        end try
        return appName & linefeed & windowName
    end tell
end run
'''
    try:
        result = _osascript(script)
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "Accessibility access unavailable"}
        lines = result.stdout.rstrip("\n").split("\n", 1)
        return {"ok": True, "application": lines[0] if lines else "",
                "window": lines[1] if len(lines) > 1 else ""}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def ui_activate(name: str) -> dict:
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        return {"ok": False, "error": "application name is required"}
    try:
        result = subprocess.run(["open", "-a", name], capture_output=True, text=True, timeout=15)
        return {"ok": result.returncode == 0, "stderr": result.stderr[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def ui_click(x, y) -> dict:
    script = '''
on run argv
    set px to item 1 of argv as integer
    set py to item 2 of argv as integer
    tell application "System Events" to click at {px, py}
end run
'''
    try:
        px, py = int(x), int(y)
        if px < 0 or py < 0 or px > 20000 or py > 20000:
            return {"ok": False, "error": "coordinates out of range"}
        result = _osascript(script, str(px), str(py))
        return {"ok": result.returncode == 0, "x": px, "y": py,
                "error": result.stderr.strip() if result.returncode else ""}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def ui_type(text: str) -> dict:
    if not isinstance(text, str):
        return {"ok": False, "error": "text must be a string"}
    if len(text) > MAX_TYPED_CHARS:
        return {"ok": False, "error": f"text exceeds {MAX_TYPED_CHARS} characters"}
    script = '''
on run argv
    tell application "System Events" to keystroke (item 1 of argv)
end run
'''
    try:
        result = _osascript(script, text, timeout=30)
        return {"ok": result.returncode == 0,
                "error": result.stderr.strip() if result.returncode else ""}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def ui_key(key: str, modifiers=None) -> dict:
    if not isinstance(key, str) or not key:
        return {"ok": False, "error": "key is required"}
    mods = modifiers or []
    if not isinstance(mods, list) or any(mod not in MODIFIERS for mod in mods):
        return {"ok": False, "error": "invalid modifier"}
    using = ""
    if mods:
        using = " using {" + ", ".join(MODIFIERS[mod] for mod in mods) + "}"
    lowered = key.lower()
    if lowered in KEY_CODES:
        script = f'tell application "System Events" to key code {KEY_CODES[lowered]}{using}'
        args = ()
    elif len(key) == 1:
        script = f'''on run argv\n tell application "System Events" to keystroke (item 1 of argv){using}\nend run'''
        args = (key,)
    else:
        return {"ok": False, "error": "key must be a supported named key or one character"}
    try:
        result = _osascript(script, *args)
        return {"ok": result.returncode == 0, "key": key, "modifiers": mods,
                "error": result.stderr.strip() if result.returncode else ""}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def execute_ui(action: str, params: dict, cfg: dict) -> dict | None:
    if action == "screen.capture":
        return screen_capture(cfg["base_dir"], params.get("display"), bool(params.get("include_base64", True)))
    if action == "ui.frontmost":
        return ui_frontmost()
    if action == "ui.activate":
        return ui_activate(params.get("name", ""))
    if action == "ui.click":
        return ui_click(params.get("x"), params.get("y"))
    if action == "ui.type":
        return ui_type(params.get("text", ""))
    if action == "ui.key":
        return ui_key(params.get("key", ""), params.get("modifiers", []))
    return None
