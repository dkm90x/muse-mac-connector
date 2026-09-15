"""Manage the outbound Cloudflare Quick Tunnel used by Muse."""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time

from . import config

_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


class TunnelManager:
    def __init__(self):
        config.ensure_dirs()
        self.proc: subprocess.Popen | None = None
        self.public_url = ""
        self.log_path = config.LOG_DIR / "tunnel.log"
        self.pid_path = config.APP_SUPPORT_DIR / "tunnel.pid"
        self._watcher: threading.Thread | None = None
        if self.is_running():
            self._restore_url()

    @staticmethod
    def installed() -> bool:
        return shutil.which("cloudflared") is not None

    def _read_pid(self) -> int | None:
        try:
            return int(self.pid_path.read_text().strip())
        except (OSError, ValueError):
            return None

    def _write_pid(self, pid: int) -> None:
        self.pid_path.write_text(f"{pid}\n")

    def _pid_is_tunnel(self, pid: int) -> bool:
        try:
            result = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True, text=True, timeout=2,
            )
            text = result.stdout
            return result.returncode == 0 and "cloudflared" in text and "127.0.0.1:8899" in text
        except (OSError, subprocess.TimeoutExpired):
            return False

    def is_running(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        pid = self._read_pid()
        return bool(pid and self._pid_is_tunnel(pid))

    def _restore_url(self) -> None:
        try:
            matches = _URL_RE.findall(self.log_path.read_text())
            if matches:
                self.public_url = matches[-1]
        except OSError:
            pass

    def start(self) -> bool:
        if self.is_running():
            self._restore_url()
            return True
        if not self.installed():
            return False
        self.public_url = ""
        log_file = open(self.log_path, "w")
        try:
            self.proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{config.AGENT_PORT}"],
                stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True,
            )
        except FileNotFoundError:
            log_file.close()
            return False
        finally:
            try:
                log_file.close()
            except OSError:
                pass
        self._write_pid(self.proc.pid)
        self._watcher = threading.Thread(target=self._watch_for_url, daemon=True)
        self._watcher.start()
        return True

    def _watch_for_url(self) -> None:
        for _ in range(60):
            if self.proc is not None and self.proc.poll() is not None:
                return
            try:
                matches = _URL_RE.findall(self.log_path.read_text())
                if matches:
                    self.public_url = matches[-1]
                    return
            except OSError:
                pass
            time.sleep(1)

    def stop(self) -> None:
        pid = self.proc.pid if self.proc is not None and self.proc.poll() is None else self._read_pid()
        if pid and self._pid_is_tunnel(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        self.proc = None
        self.public_url = ""
        try:
            self.pid_path.unlink()
        except FileNotFoundError:
            pass
