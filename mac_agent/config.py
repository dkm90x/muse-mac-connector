"""Load, validate, and update Muse Mac Connector configuration."""
from __future__ import annotations

import os
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
    }
    with destination.open("w") as handle:
        yaml.safe_dump(payload, handle, default_flow_style=False, sort_keys=False)
    return destination


def enable_packs(packs: list[str], path: str | None = None) -> dict:
    cfg = load_config(path)
    if packs == ["all"] or "all" in packs:
        selected = list(FULL_OPERATOR_PACKS)
        cfg["mode"] = "full"
        cfg["enabled_packs"] = selected
        cfg["allowed_actions"] = actions_for_packs(selected)
        cfg["confirm_actions"] = [a for a in FULL_OPERATOR_CONFIRM_ACTIONS if a in cfg["allowed_actions"]]
    else:
        selected = list(cfg.get("enabled_packs", []))
        for pack in packs:
            if pack not in FULL_OPERATOR_PACKS:
                raise ValueError(f"unknown capability pack: {pack}")
            if pack not in selected:
                selected.append(pack)
        cfg["mode"] = "restricted"
        cfg["enabled_packs"] = selected
        cfg["allowed_actions"] = actions_for_packs(selected)
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
