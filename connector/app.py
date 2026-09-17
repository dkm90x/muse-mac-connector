"""macOS menu bar UI for the unofficial Meta Muse Mac Connector."""
from __future__ import annotations

import subprocess
import threading
import time
import webbrowser

import rumps
from rumps import rumps as _rumps_impl

from . import __version__, config
from .agent_mgr import AgentManager
from .tunnel_mgr import TunnelManager

MUSE_CHAT_URL = "https://muse.ai"
ONBOARDING_MARKER = config.APP_SUPPORT_DIR / "onboarding-v0.5-shown"

HOW_TO_USE = """You only need to remember one thing: open the app, then paste into Muse.

1. OPEN MUSE MAC CONNECTOR
Double-click Muse Mac Connector.app. Look for the small circle in the top menu bar. The app starts your Mac connection for you.

2. WAIT FOR READY
The connector creates your free Cloudflare connection automatically. When it is ready, the Muse setup is copied to your clipboard automatically.

3. OPEN MUSE
Choose Connect to Muse from the menu if you want the app to open Muse for you.

4. PASTE
In Muse, press Command-V and send the copied setup. Muse can then read the connector's capability index and use the Mac tools you have enabled.

5. IF MUSE NEEDS FULL COMPUTER ACCESS
Muse can request Full Computer Mode. Your Mac will show an approval dialog. If you approve it, the running connector switches immediately — no config edit or restart.

6. IF MUSE ASKS FOR THE ACCESS KEY
Click the menu-bar circle, choose Copy Muse Access Key, and paste it only into Muse's secure credential field. Do not paste the key into normal chat.

IF YOU RESTART OR THE CONNECTION BREAKS
Open Muse Mac Connector again, or choose Reconnect & Copy Setup from the menu. Wait for the Ready notification, then paste into Muse. That's it.

You do not need to set up Cloudflare, buy a domain, run Terminal commands, or remember a URL."""

def _handle_application_reopen(delegate, ns_app, has_visible_windows):
    """Treat reopening the already-running .app as reconnect-and-copy."""
    state = getattr(delegate, "_app", {})
    callback = state.get("_reopen_callback") if isinstance(state, dict) else None
    if callback:
        callback()
    return True


# rumps does not implement this native macOS reopen delegate method itself.
# Registering it makes a second Finder/open launch useful instead of a no-op.
setattr(
    _rumps_impl.NSApp,
    "applicationShouldHandleReopen_hasVisibleWindows_",
    _handle_application_reopen,
)


PRIVACY_PANES = {
    "files": "x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders",
    "full_disk": "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles",
    "automation": "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation",
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "screen": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
}


class ConnectorApp(rumps.App):
    def __init__(self):
        super().__init__("Muse Mac Connector", title="◉", quit_button=None)
        self.agent = AgentManager()
        self.tunnel = TunnelManager()
        self.token = config.ensure_agent_token()
        self._copy_when_ready = True
        self._open_muse_when_ready = False
        self._show_first_run = not ONBOARDING_MARKER.exists()
        self._reopen_callback = self._handle_app_reopen

        permissions = rumps.MenuItem("Permissions & Capabilities")
        permissions.add(rumps.MenuItem("About Permissions", callback=self.copy_permissions_guide))
        permissions.add(rumps.MenuItem("Open Files & Folders Settings", callback=self.open_files_permissions))
        permissions.add(rumps.MenuItem("Open Full Disk Access Settings", callback=self.open_full_disk_access))
        permissions.add(rumps.MenuItem("Open Automation Settings", callback=self.open_automation_permissions))
        permissions.add(rumps.MenuItem("Open Accessibility Settings", callback=self.open_accessibility_permissions))
        permissions.add(rumps.MenuItem("Open Screen Recording Settings", callback=self.open_screen_permissions))

        advanced = rumps.MenuItem("Advanced Setup")
        advanced.add(rumps.MenuItem("Open Config File", callback=self.open_config))
        advanced.add(rumps.MenuItem("Open Scripts Folder", callback=self.open_scripts_folder))
        advanced.add(rumps.MenuItem("Open Connector Data Folder", callback=self.open_data_folder))

        self.menu = [
            rumps.MenuItem("Status", callback=None),
            None,
            rumps.MenuItem("How to Use — Easy Steps", callback=self.show_how_to_use),
            rumps.MenuItem("Capability Index", callback=self.show_capability_index),
            rumps.MenuItem("Enable Full Computer Mode", callback=self.enable_full_computer_mode),
            rumps.MenuItem("Connect to Muse", callback=self.connect_muse),
            rumps.MenuItem("Reconnect & Copy Setup", callback=self.restart_tunnel),
            rumps.MenuItem("Copy Connection Setup", callback=self.copy_connection_prompt),
            rumps.MenuItem("Copy Muse Access Key", callback=self.copy_access_key),
            permissions,
            advanced,
            None,
            rumps.MenuItem("Start Connector", callback=self.start_connector),
            rumps.MenuItem("Stop Connector", callback=self.stop_connector),
            rumps.MenuItem("Copy Tunnel URL", callback=self.copy_url),
            None,
            rumps.MenuItem("Pause Agent", callback=self.toggle_pause),
            rumps.MenuItem("View Agent Log", callback=self.view_log),
            None,
            rumps.MenuItem("Quit Connector", callback=self.quit_connector),
            rumps.MenuItem(f"v{__version__}", callback=None),
        ]
        self._ensure_services()
        self._refresh()

    def _notify(self, message: str) -> None:
        rumps.notification("Muse Mac Connector", "", message)

    def _ensure_services(self) -> None:
        if not self.agent.is_running():
            self.agent.start(self.token)
        if self.agent.is_running() and TunnelManager.installed() and not self.tunnel.is_running():
            self.tunnel.start()

    def _refresh(self) -> None:
        agent_status = "running" if self.agent.is_running() else "stopped"
        tunnel_status = "running" if self.tunnel.is_running() else "stopped"
        paused = " (PAUSED)" if self.agent.paused() else ""
        url = self.tunnel.public_url or "starting..."
        self.menu["Status"].title = (
            f"Agent: {agent_status}{paused} | Tunnel: {tunnel_status}\n{url}"
        )
        self.title = "◉" if self.agent.is_running() and self.tunnel.is_running() else "○"

    def _connection_prompt(self) -> str:
        return (
            "Connect to my Mac as a custom connector named 'My Mac'.\n\n"
            f"Base URL: {self.tunnel.public_url}\n"
            "Authentication: Bearer token. Ask me for the access key through Muse's secure "
            "credentials flow; do not ask me to paste the key into chat.\n\n"
            "API:\n"
            "- GET /health verifies the connector.\n"
            "- GET /capabilities returns the capability index, action schemas, and current enabled state.\n"
            "- POST /task with JSON {task_id?, action, params} requests an action.\n"
            "- GET /result/<task_id> retrieves a task result.\n\n"
            "Behavior contract:\n"
            "- When I say to use my Mac, use this connector directly.\n"
            "- Read /capabilities before deciding a Mac task cannot be done.\n"
            "- Combine advertised actions as needed to complete multi-step work.\n"
            "- Do not ask me to paste Terminal commands, installers, or scripts as a substitute for connector actions.\n"
            "- Do not extract credentials from other apps or Keychain without explicit user-directed need and local approval.\n"
            "- Request access.enable_full if broader authority is needed; it requires local approval. In Full Mode, surface OS permission needs and use general commands and UI primitives autonomously.\n\n"
            "Use this connector only when I explicitly ask you to work with my Mac."
        )

    def _copy(self, text: str) -> None:
        subprocess.run(["pbcopy"], input=text.encode(), check=False)

    def _queue_connection_copy(self, *, open_muse: bool = False) -> None:
        self._ensure_services()
        self._copy_when_ready = True
        self._open_muse_when_ready = self._open_muse_when_ready or open_muse
        self._finish_connection_copy_if_ready()

    def _finish_connection_copy_if_ready(self) -> bool:
        if not self._copy_when_ready or not self.tunnel.public_url:
            return False
        self._copy(self._connection_prompt())
        if self._open_muse_when_ready:
            webbrowser.open(MUSE_CHAT_URL)
        self._copy_when_ready = False
        self._open_muse_when_ready = False
        self._notify("Ready — Muse connection setup copied. Open Muse and press Command-V.")
        return True

    def _handle_app_reopen(self) -> None:
        # Double-clicking/opening the app again means: refresh the Quick Tunnel
        # and copy the new Muse setup when the replacement URL is ready.
        self.restart_tunnel(None)

    def _clear_access_key_later(self) -> None:
        token = self.token

        def worker():
            time.sleep(60)
            current = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
            if current == token:
                subprocess.run(["pbcopy"], input=b"", check=False)

        threading.Thread(target=worker, daemon=True).start()

    def show_how_to_use(self, _):
        rumps.alert(
            title="Muse Mac Connector — How to Use",
            message=HOW_TO_USE,
            ok="Got it",
        )
        try:
            ONBOARDING_MARKER.write_text("shown\n")
        except OSError:
            pass
        self._show_first_run = False

    def show_capability_index(self, _):
        try:
            index = self.agent.capabilities(self.token)
            lines = [f"Mode: {index['mode']}",
                     f"Filesystem: {index.get('filesystem_scope', 'unknown')}",
                     f"Commands: {index.get('command_execution', 'unknown')}", ""]
            for name, spec in index["packs"].items():
                status = "ON" if spec["enabled"] else "off"
                lines.append(f"{name}: {status} — {spec['description']}")
            message = "\n".join(lines)
        except (OSError, ValueError, KeyError) as exc:
            message = f"Cannot read the running helper's capability index: {exc}"
        rumps.alert(title="Muse Mac Connector — Capability Index", message=message, ok="Done")

    def enable_full_computer_mode(self, _):
        # The helper presents the full authority explanation and local approval dialog.
        # Use the same transition as Muse; do not leave a saved/live config mismatch.
        result = self.agent.enable_full_mode(self.token)
        self._refresh()
        if result.get("ok"):
            self._notify("Full Computer Mode enabled and verified: user-accessible files, general commands and installed apps.")
        else:
            rumps.alert(title="Full Computer Mode", message=result.get("error", "Activation failed."), ok="Done")

    def _open_privacy_pane(self, pane: str, label: str) -> None:
        url = PRIVACY_PANES[pane]
        subprocess.Popen(["open", url])
        self._notify(f"Opened {label}. Grant only the access you want this connector to have.")

    def copy_permissions_guide(self, _):
        guide = (
            "Muse Mac Connector permissions guide\n\n"
            "Restricted Mode limits file work to configured folders. Full Computer Mode removes those "
            "connector folder fences and lets Muse work anywhere your logged-in Mac account can access.\n\n"
            "macOS still controls protected data and app control. Full Disk Access may be needed for protected "
            "files; Accessibility is needed for clicking/typing; Screen Recording is needed for visual inspection; "
            "and Automation permissions may appear when controlling apps. The connector cannot silently grant "
            "those macOS permissions."
        )
        self._copy(guide)
        self._notify("Permissions guide copied.")

    def open_files_permissions(self, _):
        self._open_privacy_pane("files", "Files & Folders settings")

    def open_full_disk_access(self, _):
        self._open_privacy_pane("full_disk", "Full Disk Access settings")

    def open_automation_permissions(self, _):
        self._open_privacy_pane("automation", "Automation settings")

    def open_accessibility_permissions(self, _):
        self._open_privacy_pane("accessibility", "Accessibility settings")

    def open_screen_permissions(self, _):
        self._open_privacy_pane("screen", "Screen Recording settings")

    def open_config(self, _):
        from mac_agent.config import write_example_config
        path = config.APP_SUPPORT_DIR / "config.yaml"
        write_example_config(str(path))
        subprocess.Popen(["open", "-e", str(path)])
        self._notify("Config opened. Changes apply after restarting the connector.")

    def open_scripts_folder(self, _):
        path = config.APP_SUPPORT_DIR / "scripts"
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(path)])

    def open_data_folder(self, _):
        config.ensure_dirs()
        subprocess.Popen(["open", str(config.APP_SUPPORT_DIR)])

    def start_connector(self, _):
        self._queue_connection_copy()
        self._refresh()
        self._notify("Connector starting. Setup will copy automatically when ready.")

    def stop_connector(self, _):
        self.tunnel.stop()
        self.agent.stop()
        self._copy_when_ready = False
        self._open_muse_when_ready = False
        self._refresh()
        self._notify("Connector stopped.")

    def connect_muse(self, _):
        self._queue_connection_copy(open_muse=True)
        if not self.tunnel.public_url:
            self._notify("Starting your connection. Muse will open and setup will copy when ready.")

    def copy_connection_prompt(self, _):
        self._queue_connection_copy()
        if not self.tunnel.public_url:
            self._notify("Starting your connection. Setup will copy automatically when ready.")

    def copy_access_key(self, _):
        self._copy(self.token)
        self._clear_access_key_later()
        self._notify("Access key copied for 60 seconds. Paste it only into Muse's secure field.")

    def restart_tunnel(self, _):
        self.tunnel.stop()
        self._copy_when_ready = True
        self._open_muse_when_ready = False
        if self.agent.is_running(self.token) and self.tunnel.start():
            self._notify("Reconnecting. The new Muse setup will copy automatically when ready.")
        else:
            self._notify("Reconnect failed. Check the agent log or choose Start Connector.")
        self._refresh()

    def copy_url(self, _):
        if not self.tunnel.public_url:
            self._notify("No tunnel URL yet.")
            return
        self._copy(self.tunnel.public_url)
        self._notify("Tunnel URL copied.")

    def toggle_pause(self, sender):
        paused = not self.agent.paused()
        self.agent.set_paused(paused)
        sender.title = "Resume Agent" if paused else "Pause Agent"
        self._notify("Agent paused." if paused else "Agent resumed.")
        self._refresh()

    def view_log(self, _):
        subprocess.Popen(["open", str(self.agent.log_path)])

    def quit_connector(self, _):
        self.tunnel.stop()
        self.agent.stop()
        rumps.quit_application()

    @rumps.timer(2)
    def _tick(self, _):
        # Recover automatically if the local agent or cloudflared process exits.
        self._ensure_services()
        self._refresh()
        self._finish_connection_copy_if_ready()
        # Do not show a modal first-run dialog until the tunnel is ready.
        # Otherwise the dialog blocks the timer before the setup reaches the clipboard.
        if self._show_first_run and self.tunnel.public_url:
            self.show_how_to_use(None)


def main():
    config.ensure_dirs()
    ConnectorApp().run()


if __name__ == "__main__":
    main()
