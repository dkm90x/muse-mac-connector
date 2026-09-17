"""Capability registry for Muse Mac Connector.

The registry is the single source of truth shared by the HTTP API and CLI.
"""
from __future__ import annotations

PACKS = {
    "files": {
        "description": "Inspect and modify files within the current mode's filesystem authority.",
        "actions": [
            "files.list", "files.read", "files.write", "files.mkdir",
            "files.move", "files.copy", "files.trash",
        ],
    },
    "shell": {
        "description": "Run commands: general login-shell execution in Full Mode; guarded argv in Restricted Mode.",
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
ACCESS_REQUEST = "access.enable_full"

CAPABILITY_SCHEMAS = {
    ACCESS_REQUEST: {},
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
    allowed = set(available_actions(cfg))
    enabled = set(cfg.get("enabled_packs", []))
    return {
        name: {
            "description": spec["description"],
            "enabled": name in enabled or all(action in allowed for action in spec["actions"]),
            "actions": spec["actions"],
        }
        for name, spec in PACKS.items()
    }


def available_actions(cfg: dict) -> list[str]:
    actions = (actions_for_packs(FULL_OPERATOR_PACKS) if cfg.get("mode") == "full"
               else list(cfg.get("allowed_actions", [])))
    return list(dict.fromkeys([*actions, ACCESS_REQUEST]))


def capability_index(cfg: dict) -> dict:
    from .config import CONFIG_LOCK, FULL_OPERATOR_CONFIRM_ACTIONS

    with CONFIG_LOCK:
        cfg = dict(cfg)
    full = cfg.get("mode") == "full"
    confirm = set(cfg.get("confirm_actions", [])) | {ACCESS_REQUEST}
    if full:
        confirm.update(FULL_OPERATOR_CONFIRM_ACTIONS)
    actions = {}
    for name in available_actions(cfg):
        actions[name] = {
            "params": CAPABILITY_SCHEMAS.get(name, {}),
            "confirmation_required": name in confirm,
            "confirmation_policy": (
                "always_local" if name in confirm else
                "high_risk_commands_local" if full and name in {"shell.exec", "process.start"} else
                "not_required"
            ),
        }
    payload = {
        "ok": True,
        "mode": "full" if full else "restricted",
        "filesystem_scope": "user_accessible" if full else "configured_roots",
        "command_execution": "general" if full else "restricted",
        "application_scope": "installed_apps" if full else "advertised_actions",
        "approval_model": {
            "enable_full": "explicit_local_approval",
            "ordinary_actions": "autonomous" if full else "configured_confirmation",
            "high_risk_commands": "local_confirmation" if full else "restricted_command_policy",
            "os_permissions": "macOS_permissions_admin_prompts_SIP_TCC_apply",
        },
        "packs": describe(cfg),
        "actions": actions,
        "policy": {
            "use_my_mac": (
                "Full Computer Mode is intended for autonomous multi-step Mac work using files, general "
                "commands, processes, installed apps, screen, keyboard, mouse and clipboard. There are "
                "no connector folder, application or workflow fences. Chain these primitives to finish the task."
                if full else "Use advertised actions within configured roots and conservative command restrictions."
            ),
            "access": "Request access.enable_full when broader authority is needed; only local approval enables it.",
            "os_permissions": "Surface OS access failures as permission needs, not connector limitations. Never bypass OS prompts or protections.",
            "terminal": "Use shell.exec or process.start for available command workflows; do not ask the user to paste substitute Terminal commands.",
            "secrets": "Do not extract credentials, tokens or secrets from other apps or Keychain without explicit user-directed need and local approval. No credential scraping helpers are provided.",
            "high_risk": "Obvious destructive, privileged and credential-sensitive commands require local confirmation. Do not disguise commands or route through other primitives to evade approval.",
            "missing_capability": "Check mode and advertised primitives first. Request Full Mode if restricted; otherwise report a genuinely missing primitive or OS permission need.",
        },
    }
    if not full:
        payload["working_roots"] = cfg.get("allowed_roots", [])
    return payload
