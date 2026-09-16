"""Computer-operator actions for Muse Mac Connector.

These actions are intentionally broader than the original alpha actions, but still
respect configured working roots and avoid invoking a shell interpreter.
"""
from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .actions import _within_roots

MAX_FILE_BYTES = 512 * 1024
MAX_PROCESS_OUTPUT = 64 * 1024
MAX_PROCESSES = 24
BLOCKED_EXECUTABLES = {
    "sudo", "su", "security", "ssh-add", "dscl", "launchctl", "osascript", "rm", "rmdir",
}
SHELL_META = ("|", ";", "&", ">", "<", "`", "$(", "\n", "\r")

_processes: dict[str, dict] = {}
_process_lock = threading.Lock()


def _resolve_allowed(path: str, roots: list[str]) -> Path:
    expanded = os.path.abspath(os.path.expanduser(path))
    if not _within_roots(expanded, roots):
        raise ValueError("path outside allowed roots")
    return Path(expanded)


def _argv(command) -> list[str]:
    if isinstance(command, str):
        if not command.strip():
            raise ValueError("command is required")
        if any(token in command for token in SHELL_META):
            raise ValueError("shell operators are not supported; pass one command at a time")
        argv = shlex.split(command)
    elif isinstance(command, list) and all(isinstance(item, str) for item in command):
        argv = list(command)
    else:
        raise ValueError("command must be a string or argv array")
    if not argv:
        raise ValueError("command is required")
    executable = os.path.basename(argv[0])
    if executable in BLOCKED_EXECUTABLES:
        raise ValueError(f"command is blocked in operator mode: {executable}")
    for arg in argv[1:]:
        if arg == ".." or arg.startswith("../") or "/../" in arg:
            raise ValueError("parent-directory path traversal is not allowed")
    return argv


def _validate_command_paths(argv: list[str], roots: list[str]) -> None:
    for arg in argv[1:]:
        if arg.startswith("/") or arg.startswith("~"):
            if not _within_roots(arg, roots):
                raise ValueError("absolute command path argument outside allowed roots")


def files_list(path: str, roots: list[str], recursive: bool = False, max_entries: int = 200) -> dict:
    try:
        root = _resolve_allowed(path, roots)
        if not root.is_dir():
            return {"ok": False, "error": "path is not a directory"}
        limit = max(1, min(int(max_entries), 1000))
        iterator = root.rglob("*") if recursive else root.iterdir()
        entries = []
        for item in iterator:
            entries.append({
                "name": item.name,
                "path": str(item),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
            if len(entries) >= limit:
                break
        return {"ok": True, "path": str(root), "entries": entries, "truncated": len(entries) >= limit}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def files_read(path: str, roots: list[str], max_bytes: int = MAX_FILE_BYTES) -> dict:
    try:
        target = _resolve_allowed(path, roots)
        if not target.is_file():
            return {"ok": False, "error": "path is not a file"}
        limit = max(1, min(int(max_bytes), MAX_FILE_BYTES))
        raw = target.read_bytes()
        if len(raw) > limit:
            raw = raw[:limit]
            truncated = True
        else:
            truncated = False
        return {"ok": True, "path": str(target), "content": raw.decode("utf-8", errors="replace"),
                "truncated": truncated}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def files_write(path: str, content: str, roots: list[str], append: bool = False) -> dict:
    if not isinstance(content, str):
        return {"ok": False, "error": "content must be a string"}
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        return {"ok": False, "error": f"content exceeds {MAX_FILE_BYTES} bytes"}
    try:
        target = _resolve_allowed(path, roots)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if append else "w", encoding="utf-8") as handle:
            handle.write(content)
        return {"ok": True, "path": str(target), "bytes": len(content.encode("utf-8")), "append": bool(append)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def files_mkdir(path: str, roots: list[str]) -> dict:
    try:
        target = _resolve_allowed(path, roots)
        target.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "path": str(target)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def files_trash(path: str, roots: list[str]) -> dict:
    try:
        target = _resolve_allowed(path, roots)
        if not target.exists():
            return {"ok": False, "error": "path does not exist"}
        trash = Path.home() / ".Trash"
        trash.mkdir(exist_ok=True)
        destination = trash / target.name
        if destination.exists():
            destination = trash / f"{target.stem}-{int(time.time())}{target.suffix}"
        shutil.move(str(target), str(destination))
        return {"ok": True, "path": str(target), "trashed_to": str(destination)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def shell_exec(command, cwd: str, roots: list[str], timeout: int = 300) -> dict:
    try:
        workdir = _resolve_allowed(cwd, roots)
        argv = _argv(command)
        _validate_command_paths(argv, roots)
        limit = max(1, min(int(timeout), 900))
        result = subprocess.run(argv, cwd=workdir, capture_output=True, text=True, timeout=limit)
        return {"ok": result.returncode == 0, "argv": argv, "cwd": str(workdir),
                "stdout": result.stdout[-MAX_PROCESS_OUTPUT:], "stderr": result.stderr[-MAX_PROCESS_OUTPUT:],
                "returncode": result.returncode}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "error": f"command timed out after {timeout}s",
                "stdout": (exc.stdout or "")[-MAX_PROCESS_OUTPUT:] if isinstance(exc.stdout, str) else ""}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def process_start(command, cwd: str, roots: list[str], base_dir: str) -> dict:
    try:
        workdir = _resolve_allowed(cwd, roots)
        argv = _argv(command)
        _validate_command_paths(argv, roots)
        with _process_lock:
            running = sum(1 for item in _processes.values() if item["proc"].poll() is None)
            if running >= MAX_PROCESSES:
                return {"ok": False, "error": "process limit reached"}
        process_id = uuid.uuid4().hex[:12]
        log_dir = Path(base_dir) / "process-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{process_id}.log"
        log_handle = log_path.open("ab")
        proc = subprocess.Popen(argv, cwd=workdir, stdout=log_handle, stderr=subprocess.STDOUT,
                                start_new_session=True)
        log_handle.close()
        with _process_lock:
            _processes[process_id] = {"proc": proc, "argv": argv, "cwd": str(workdir), "log": str(log_path)}
        return {"ok": True, "process_id": process_id, "pid": proc.pid, "argv": argv, "cwd": str(workdir)}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def _process_entry(process_id: str):
    with _process_lock:
        return _processes.get(process_id)


def process_status(process_id: str) -> dict:
    entry = _process_entry(process_id)
    if not entry:
        return {"ok": False, "error": "unknown process"}
    code = entry["proc"].poll()
    return {"ok": True, "process_id": process_id, "pid": entry["proc"].pid,
            "running": code is None, "returncode": code, "argv": entry["argv"], "cwd": entry["cwd"]}


def process_output(process_id: str, max_bytes: int = 16384) -> dict:
    entry = _process_entry(process_id)
    if not entry:
        return {"ok": False, "error": "unknown process"}
    try:
        limit = max(1, min(int(max_bytes), MAX_PROCESS_OUTPUT))
        data = Path(entry["log"]).read_bytes()
        return {"ok": True, "process_id": process_id,
                "output": data[-limit:].decode("utf-8", errors="replace"),
                "running": entry["proc"].poll() is None}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def process_kill(process_id: str) -> dict:
    entry = _process_entry(process_id)
    if not entry:
        return {"ok": False, "error": "unknown process"}
    proc = entry["proc"]
    if proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as exc:
            return {"ok": False, "error": str(exc)}
    return {"ok": True, "process_id": process_id}


def app_open(name: str) -> dict:
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        return {"ok": False, "error": "application name is required"}
    try:
        result = subprocess.run(["open", "-a", name], capture_output=True, text=True, timeout=15)
        return {"ok": result.returncode == 0, "stderr": result.stderr[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def clipboard_read() -> dict:
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        return {"ok": result.returncode == 0, "text": result.stdout[-MAX_FILE_BYTES:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def clipboard_write(text: str) -> dict:
    if not isinstance(text, str):
        return {"ok": False, "error": "text must be a string"}
    try:
        result = subprocess.run(["pbcopy"], input=text, text=True, timeout=5)
        return {"ok": result.returncode == 0}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc)}


def execute_operator(action: str, params: dict, cfg: dict) -> dict | None:
    roots = cfg.get("allowed_roots", [])
    if action == "files.list":
        return files_list(params.get("path", ""), roots, bool(params.get("recursive", False)), params.get("max_entries", 200))
    if action == "files.read":
        return files_read(params.get("path", ""), roots, params.get("max_bytes", MAX_FILE_BYTES))
    if action == "files.write":
        return files_write(params.get("path", ""), params.get("content", ""), roots, bool(params.get("append", False)))
    if action == "files.mkdir":
        return files_mkdir(params.get("path", ""), roots)
    if action == "files.trash":
        return files_trash(params.get("path", ""), roots)
    if action == "shell.exec":
        return shell_exec(params.get("command", ""), params.get("cwd", ""), roots, params.get("timeout", 300))
    if action == "process.start":
        return process_start(params.get("command", ""), params.get("cwd", ""), roots, cfg["base_dir"])
    if action == "process.status":
        return process_status(str(params.get("process_id", "")))
    if action == "process.output":
        return process_output(str(params.get("process_id", "")), params.get("max_bytes", 16384))
    if action == "process.kill":
        return process_kill(str(params.get("process_id", "")))
    if action == "app.open":
        return app_open(params.get("name", ""))
    if action == "clipboard.read":
        return clipboard_read()
    if action == "clipboard.write":
        return clipboard_write(params.get("text", ""))
    return None
