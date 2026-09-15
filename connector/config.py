"""Paths, secrets, and settings for the Muse Mac Connector."""
from __future__ import annotations

import os
import secrets
import subprocess
from pathlib import Path

HOME = Path.home()
APP_SUPPORT_DIR = HOME / "Library" / "Application Support" / "Muse Mac Connector"
LOG_DIR = APP_SUPPORT_DIR / "logs"
PAUSED_FILE = APP_SUPPORT_DIR / "PAUSED"
FALLBACK_TOKEN_FILE = APP_SUPPORT_DIR / "access-key"
LEGACY_TOKEN_FILE = HOME / ".mac-connector-token"
KEYCHAIN_SERVICE = "com.musemacconnector.access-key"
KEYCHAIN_ACCOUNT = "default"

AGENT_PORT = 8899
AGENT_URL = f"http://127.0.0.1:{AGENT_PORT}"
AGENT_MODULE = "mac_agent"


def ensure_dirs() -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _keychain_get() -> str:
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", KEYCHAIN_SERVICE,
             "-a", KEYCHAIN_ACCOUNT, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _keychain_set(token: str) -> bool:
    try:
        result = subprocess.run(
            ["/usr/bin/security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
             "-a", KEYCHAIN_ACCOUNT, "-w", token],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _read_file_token(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _write_fallback_token(token: str) -> None:
    ensure_dirs()
    FALLBACK_TOKEN_FILE.write_text(token + "\n")
    os.chmod(FALLBACK_TOKEN_FILE, 0o600)


def ensure_agent_token() -> str:
    """Return the access key, preferring macOS Keychain and migrating legacy installs."""
    ensure_dirs()
    token = _keychain_get()
    if token:
        return token

    for path in (LEGACY_TOKEN_FILE, FALLBACK_TOKEN_FILE):
        token = _read_file_token(path)
        if not token:
            continue
        if _keychain_set(token):
            try:
                path.unlink()
            except OSError:
                pass
        return token

    token = secrets.token_hex(32)
    if not _keychain_set(token):
        _write_fallback_token(token)
    return token
