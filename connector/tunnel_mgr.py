"""Manage the outbound transport used by Muse: Quick Tunnel or stable VPS relay."""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import threading
import time
import sys
from pathlib import Path

from . import config
from mac_agent.config import load_config

_URL_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


class TunnelManager:
    def __init__(self):
        config.ensure_dirs()
        self.proc: subprocess.Popen | None = None
        self.settings = load_config()
        self.public_url = ""
        self.log_path = config.LOG_DIR / "tunnel.log"
        self.pid_path = config.APP_SUPPORT_DIR / "tunnel.pid"
        self._watcher: threading.Thread | None = None
        if self.is_running():
            self._restore_url()

    @staticmethod
    def cloudflared_path() -> str | None:
        """Find a bundled cloudflared first, then common local installs/PATH."""
        if getattr(sys, "frozen", False):
            bundled = Path(sys.executable).resolve().parents[1] / "Resources" / "cloudflared"
            if bundled.is_file() and os.access(bundled, os.X_OK):
                return str(bundled)
        for candidate in ("/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"):
            if Path(candidate).is_file() and os.access(candidate, os.X_OK):
                return candidate
        return shutil.which("cloudflared")

    @staticmethod
    def ssh_path() -> str | None:
        candidate = Path("/usr/bin/ssh")
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return shutil.which("ssh")

    def _reload_settings(self) -> None:
        self.settings = load_config()

    def installed(self) -> bool:
        self._reload_settings()
        if self.settings.get("transport_mode") == "vps_relay":
            identity = Path(str(self.settings.get("relay_identity_file", "")))
            return bool(self.ssh_path() and self.settings.get("relay_host") and
                        self.settings.get("relay_public_url") and identity.is_file())
        return self.cloudflared_path() is not None

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
            quick = "cloudflared" in text and f"127.0.0.1:{config.AGENT_PORT}" in text
            relay = "ssh" in text and " -R " in f" {text} " and f"127.0.0.1:{config.AGENT_PORT}" in text
            return result.returncode == 0 and (quick or relay)
        except (OSError, subprocess.TimeoutExpired):
            return False

    def is_running(self) -> bool:
        if self.proc is not None and self.proc.poll() is None:
            return True
        pid = self._read_pid()
        return bool(pid and self._pid_is_tunnel(pid))

    def _restore_url(self) -> None:
        self._reload_settings()
        if self.settings.get("transport_mode") == "vps_relay":
            self.public_url = str(self.settings.get("relay_public_url", "")).rstrip("/")
            return
        try:
            matches = _URL_RE.findall(self.log_path.read_text())
            if matches:
                self.public_url = matches[-1]
        except OSError:
            pass

    def _command(self) -> list[str] | None:
        self._reload_settings()
        if self.settings.get("transport_mode") == "vps_relay":
            ssh = self.ssh_path()
            host = str(self.settings.get("relay_host", ""))
            user = str(self.settings.get("relay_user", "lifeos-relay"))
            identity = str(self.settings.get("relay_identity_file", ""))
            if not ssh or not host or not user or not Path(identity).is_file():
                return None
            remote_port = int(self.settings.get("relay_remote_port", 18899))
            ssh_port = int(self.settings.get("relay_ssh_port", 22))
            return [
                ssh, "-N", "-T", "-i", identity, "-p", str(ssh_port),
                "-o", "BatchMode=yes", "-o", "ExitOnForwardFailure=yes",
                "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
                "-o", "StrictHostKeyChecking=yes",
                "-R", f"127.0.0.1:{remote_port}:127.0.0.1:{config.AGENT_PORT}",
                f"{user}@{host}",
            ]
        cloudflared = self.cloudflared_path()
        if not cloudflared:
            return None
        return [cloudflared, "tunnel", "--url", f"http://127.0.0.1:{config.AGENT_PORT}"]

    def start(self) -> bool:
        if self.is_running():
            self._restore_url()
            return True
        command = self._command()
        if not command:
            return False
        self.public_url = ""
        if self.settings.get("transport_mode") == "vps_relay":
            self.public_url = str(self.settings.get("relay_public_url", "")).rstrip("/")
        log_file = open(self.log_path, "w")
        try:
            self.proc = subprocess.Popen(
                command, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True,
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
        if self.settings.get("transport_mode") != "vps_relay":
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
