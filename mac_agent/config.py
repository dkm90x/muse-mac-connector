"""Load, validate, and update Muse Mac Connector configuration."""
from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

import yaml

from .capabilities import FULL_OPERATOR_PACKS, actions_for_packs

DEFAULT_ACTIONS = [
    "shortcuts.run",
    "files.move",
    "files.copy",
    "settings.defaults",
    "system.open_url",
    "shell.script",
]

DEFAULTS = {
    "base_dir": "~/Library/Application Support/Muse Mac Connector",
    "mode": "restricted",
    "enabled_packs": [],
    "allowed_roots": ["~/Downloads", "~/Desktop", "~/Documents"],
    "allowed_actions": list(DEFAULT_ACTIONS),
    "confirm_actions": list(DEFAULT_ACTIONS),
    "scripts_dir": "~/Library/Application Support/Muse Mac Connector/scripts",
}

# Full Computer Mode is an explicit opt-in. Reversible/destructive operations still
# keep a local confirmation gate; ordinary development operations can run unattended.
FULL_OPERATOR_CONFIRM_ACTIONS = ["files.trash", "settings.defaults"]
CONFIG_LOCK = threading.RLock()

FULL_MODE_CONSENT = (
    "Enable Full Computer Mode? Muse will be able to read, write, create, move and trash files "
    "anywhere your Mac account can access, run general Terminal commands, manage processes, "
    "operate installed apps, and use screen, keyboard, mouse and clipboard autonomously. "
    "Configured working folders will no longer limit access. macOS permissions, admin/password "
    "prompts and SIP/TCC still apply. Destructive, privileged and credential-sensitive commands "
    "still require local approval. Only allow this if you trust the connected agent."
)


def full_mode_config(cfg: dict) -> dict:
    return {**cfg, "mode": "full", "enabled_packs": list(FULL_OPERATOR_PACKS),
            "allowed_actions": actions_for_packs(FULL_OPERATOR_PACKS),
            "confirm_actions": list(FULL_OPERATOR_CONFIRM_ACTIONS)}


def apply_full_mode(cfg: dict) -> None:
    """Persist before mutating the shared config. Caller must obtain local consent."""
    with CONFIG_LOCK:
        updated = full_mode_config(cfg)
        save_config(updated, cfg.get("_config_path"))
        cfg.update(updated)


def _expand(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def config_path(path: str | None = None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path(_expand(DEFAULTS["base_dir"])) / "config.yaml"


def load_config(path: str | None = None) -> dict:
    cfg_path = config_path(path)
    cfg = dict(DEFAULTS)
    for key in ("enabled_packs", "allowed_roots", "allowed_actions", "confirm_actions"):
        cfg[key] = list(DEFAULTS[key])
    if cfg_path.exists():
        with cfg_path.open() as handle:
            user_cfg = yaml.safe_load(handle) or {}
        if not isinstance(user_cfg, dict):
            raise ValueError("config.yaml must contain a mapping")
        cfg.update(user_cfg)

    cfg["base_dir"] = _expand(str(cfg["base_dir"]))
    cfg["scripts_dir"] = _expand(str(cfg["scripts_dir"]))
    cfg["mode"] = str(cfg.get("mode", "restricted"))
    cfg["enabled_packs"] = [str(p) for p in cfg.get("enabled_packs", [])]
    cfg["allowed_roots"] = [_expand(str(p)) for p in cfg.get("allowed_roots", [])]
    cfg["allowed_actions"] = [str(a) for a in cfg.get("allowed_actions", [])]
    cfg["confirm_actions"] = [str(a) for a in cfg.get("confirm_actions", [])]
    cfg["_config_path"] = str(cfg_path.absolute())
    return cfg


def save_config(cfg: dict, path: str | None = None) -> Path:
    destination = config_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": cfg.get("mode", "restricted"),
        "enabled_packs": list(cfg.get("enabled_packs", [])),
        "allowed_roots": list(cfg.get("allowed_roots", [])),
        "allowed_actions": list(cfg.get("allowed_actions", [])),
        "confirm_actions": list(cfg.get("confirm_actions", [])),
        "scripts_dir": cfg.get("scripts_dir", DEFAULTS["scripts_dir"]),
        "base_dir": cfg.get("base_dir", DEFAULTS["base_dir"]),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False) as handle:
            temporary = handle.name
            yaml.safe_dump(payload, handle, default_flow_style=False, sort_keys=False)
        os.replace(temporary, destination)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def enable_packs(packs: list[str], path: str | None = None) -> dict:
    cfg = load_config(path)
    if packs == ["all"] or "all" in packs:
        cfg = full_mode_config(cfg)
    else:
        selected = list(cfg.get("enabled_packs", []))
        for pack in packs:
            if pack not in FULL_OPERATOR_PACKS:
                raise ValueError(f"unknown capability pack: {pack}")
            if pack not in selected:
                selected.append(pack)
        cfg["mode"] = "restricted"
        cfg["enabled_packs"] = selected
        added = actions_for_packs(packs)
        cfg["allowed_actions"] = list(dict.fromkeys([*cfg.get("allowed_actions", []), *added]))
        cfg["confirm_actions"] = list(cfg["allowed_actions"])
    save_config(cfg, path)
    return load_config(path)


def write_example_config(path: str) -> None:
    destination = Path(os.path.expanduser(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    with destination.open("w") as handle:
        yaml.safe_dump(DEFAULTS, handle, default_flow_style=False, sort_keys=False)
