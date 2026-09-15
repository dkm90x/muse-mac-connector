"""Load and validate the Muse Mac Connector configuration."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULTS = {
    "base_dir": "~/Library/Application Support/Muse Mac Connector",
    "allowed_roots": ["~/Downloads", "~/Desktop", "~/Documents"],
    "allowed_actions": [
        "shortcuts.run",
        "files.move",
        "files.copy",
        "settings.defaults",
        "system.open_url",
        "shell.script",
    ],
    "confirm_actions": [
        "shortcuts.run",
        "files.move",
        "files.copy",
        "settings.defaults",
        "system.open_url",
        "shell.script",
    ],
    "scripts_dir": "~/Library/Application Support/Muse Mac Connector/scripts",
}


def _expand(value: str) -> str:
    return os.path.abspath(os.path.expanduser(value))


def load_config(path: str | None = None) -> dict:
    base = Path(_expand(DEFAULTS["base_dir"]))
    cfg_path = Path(path).expanduser() if path else base / "config.yaml"
    cfg = dict(DEFAULTS)
    cfg["allowed_roots"] = list(DEFAULTS["allowed_roots"])
    cfg["allowed_actions"] = list(DEFAULTS["allowed_actions"])
    cfg["confirm_actions"] = list(DEFAULTS["confirm_actions"])
    if cfg_path.exists():
        with cfg_path.open() as handle:
            user_cfg = yaml.safe_load(handle) or {}
        if not isinstance(user_cfg, dict):
            raise ValueError("config.yaml must contain a mapping")
        cfg.update(user_cfg)

    cfg["base_dir"] = _expand(str(cfg["base_dir"]))
    cfg["scripts_dir"] = _expand(str(cfg["scripts_dir"]))
    cfg["allowed_roots"] = [_expand(str(p)) for p in cfg.get("allowed_roots", [])]
    cfg["allowed_actions"] = [str(a) for a in cfg.get("allowed_actions", [])]
    cfg["confirm_actions"] = [str(a) for a in cfg.get("confirm_actions", [])]
    return cfg


def write_example_config(path: str) -> None:
    destination = Path(os.path.expanduser(path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    with destination.open("w") as handle:
        yaml.safe_dump(DEFAULTS, handle, default_flow_style=False, sort_keys=False)
