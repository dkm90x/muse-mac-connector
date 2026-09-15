"""Manage the authenticated Mac Agent subprocess."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config


class AgentManager:
    def __init__(self):
        config.ensure_dirs()
        self.proc: subprocess.Popen | None = None
        self.log_path = config.LOG_DIR / "agent.log"
        self.pid_path = config.APP_SUPPORT_DIR / "agent.pid"

    def _read_pid(self) -> int | None:
        try:
            return int(self.pid_path.read_text().strip())
        except (OSError, ValueError):
            return None

    def _write_pid(self, pid: int) -> None:
        self.pid_path.write_text(f"{pid}\n")

    def _pid_is_agent(self, pid: int) -> bool:
        try:
            result = subprocess.run(
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True, text=True, timeout=2,
            )
            return result.returncode == 0 and "mac_agent" in result.stdout and "--http" in result.stdout
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _health(self, token: str) -> bool:
        request = urllib.request.Request(
            f"http://127.0.0.1:{config.AGENT_PORT}/health",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1) as response:
                return json.loads(response.read()).get("ok") is True
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return False

    def is_running(self, token: str = "") -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        token = token or config.ensure_agent_token()
        return self._health(token)

    def start(self, token: str = "") -> bool:
        token = token or config.ensure_agent_token()
        if self.is_running(token):
            return True

        env = dict(os.environ)
        env["MAC_AGENT_TOKEN"] = token
        repo_root = str(Path(__file__).resolve().parents[1])
        env["PYTHONPATH"] = repo_root + os.pathsep + env.get("PYTHONPATH", "")
        log_file = open(self.log_path, "a")
        try:
            self.proc = subprocess.Popen(
                [sys.executable, "-m", config.AGENT_MODULE, "--http"],
                stdout=log_file, stderr=subprocess.STDOUT, env=env,
                start_new_session=True,
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
        for _ in range(20):
            if self.proc.poll() is not None:
                break
            if self._health(token):
                return True
            time.sleep(0.25)
        self.stop()
        return False

    def stop(self) -> None:
        pid = self.proc.pid if self.proc is not None and self.proc.poll() is None else self._read_pid()
        if pid and self._pid_is_agent(pid):
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        self.proc = None
        try:
            self.pid_path.unlink()
        except FileNotFoundError:
            pass

    def recent_log(self, lines: int = 20) -> str:
        try:
            with self.log_path.open() as handle:
                return "".join(handle.readlines()[-lines:])
        except FileNotFoundError:
            return "(no log yet)"

    def paused(self) -> bool:
        return config.PAUSED_FILE.exists()

    def set_paused(self, paused: bool) -> None:
        config.ensure_dirs()
        if paused:
            config.PAUSED_FILE.touch()
        else:
            try:
                config.PAUSED_FILE.unlink()
            except FileNotFoundError:
                pass
