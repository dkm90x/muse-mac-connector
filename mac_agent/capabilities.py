"""Capability registry for Muse Mac Connector.

The registry is the single source of truth shared by the HTTP API and CLI.
"""
from __future__ import annotations

PACKS = {
    "files": {
        "description": "Inspect and modify files inside configured working roots.",
        "actions": [
            "files.list", "files.read", "files.write", "files.mkdir",
            "files.move", "files.copy", "files.trash",
        ],
    },
    "shell": {
        "description": "Run developer commands without invoking a shell interpreter.",
        "actions": ["shell.exec"],
    },
    "processes": {
        "description": "Start and supervise long-running developer processes.",
        "actions": ["process.start", "process.status", "process.output", "process.kill"],
    },
    "apps": {
        "description": "Launch installed macOS applications.",
        "actions": ["app.open"],
    },
    "clipboard": {
        "description": "Read and write the current user's clipboard.",
        "actions": ["clipboard.read", "clipboard.write"],
    },
    "screen": {
        "description": "Capture the Mac display for visual inspection. Requires Screen Recording permission.",
        "actions": ["screen.capture"],
    },
    "ui": {
        "description": "Inspect and operate the visible Mac UI. Requires Accessibility permission.",
        "actions": ["ui.frontmost", "ui.activate", "ui.click", "ui.type", "ui.key"],
    },
    "shortcuts": {
        "description": "Run Apple Shortcuts by name.",
        "actions": ["shortcuts.run"],
    },
    "web": {
        "description": "Open HTTP(S) URLs on the Mac.",
        "actions": ["system.open_url"],
    },
    "scripts": {
        "description": "Run executable scripts deliberately placed in the connector scripts folder.",
        "actions": ["shell.script"],
    },
    "settings": {
        "description": "Change explicitly requested macOS defaults string values.",
        "actions": ["settings.defaults"],
    },
}

FULL_OPERATOR_PACKS = tuple(PACKS)

CAPABILITY_SCHEMAS = {
    "files.list": {"path": "path", "recursive": "bool (optional)", "max_entries": "int (optional)"},
    "files.read": {"path": "path", "max_bytes": "int (optional)"},
    "files.write": {"path": "path", "content": "string", "append": "bool (optional)"},
    "files.mkdir": {"path": "path"},
    "files.move": {"src": "path", "dst": "path"},
    "files.copy": {"src": "path", "dst": "path"},
    "files.trash": {"path": "path"},
    "shell.exec": {"command": "string or argv[]", "cwd": "path", "timeout": "seconds (optional)"},
    "process.start": {"command": "string or argv[]", "cwd": "path"},
    "process.status": {"process_id": "string"},
    "process.output": {"process_id": "string", "max_bytes": "int (optional)"},
    "process.kill": {"process_id": "string"},
    "app.open": {"name": "application name"},
    "clipboard.read": {},
    "clipboard.write": {"text": "string"},
    "screen.capture": {"display": "int (optional)", "include_base64": "bool (optional)"},
    "ui.frontmost": {},
    "ui.activate": {"name": "application name"},
    "ui.click": {"x": "int", "y": "int"},
    "ui.type": {"text": "string"},
    "ui.key": {"key": "return|tab|escape|delete|space|up|down|left|right|home|end|pageup|pagedown", "modifiers": "array (optional)"},
    "shortcuts.run": {"name": "string", "input": "string (optional)"},
    "settings.defaults": {"domain": "string", "key": "string", "value": "string"},
    "system.open_url": {"url": "http(s) URL"},
    "shell.script": {"name": "pre-registered executable script filename"},
}


def actions_for_packs(packs: list[str] | tuple[str, ...]) -> list[str]:
    """Return a de-duplicated action list in registry order."""
    actions: list[str] = []
    for pack in packs:
        spec = PACKS.get(pack)
        if not spec:
            raise ValueError(f"unknown capability pack: {pack}")
        for action in spec["actions"]:
            if action not in actions:
                actions.append(action)
    return actions


def describe(cfg: dict) -> dict:
    allowed = set(cfg.get("allowed_actions", []))
    enabled = set(cfg.get("enabled_packs", []))
    return {
        name: {
            "description": spec["description"],
            "enabled": name in enabled or all(action in allowed for action in spec["actions"]),
            "actions": spec["actions"],
        }
        for name, spec in PACKS.items()
    }
