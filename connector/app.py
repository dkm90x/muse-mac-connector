"""macOS menu bar UI for the unofficial Meta Muse Mac Connector."""
from __future__ import annotations

import subprocess
import threading
import time
import webbrowser

import rumps

from . import __version__, config
from .agent_mgr import AgentManager
from .tunnel_mgr import TunnelManager

MUSE_CHAT_URL = "https://muse.ai"

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
            rumps.MenuItem("Connect to Muse", callback=self.connect_muse),
            rumps.MenuItem("Copy Connection Prompt", callback=self.copy_connection_prompt),
            rumps.MenuItem("Copy Muse Access Key", callback=self.copy_access_key),
            permissions,
            advanced,
            None,
            rumps.MenuItem("Start Connector", callback=self.start_connector),
            rumps.MenuItem("Stop Connector", callback=self.stop_connector),
            rumps.MenuItem("Restart Tunnel", callback=self.restart_tunnel),
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
            "- GET /capabilities returns allowed actions and whether confirmation is required.\n"
            "- POST /task with JSON {task_id?, action, params} requests an action.\n"
            "- GET /result/<task_id> retrieves a task result.\n\n"
            "Use this connector only when I explicitly ask you to work with my Mac."
        )

    def _copy(self, text: str) -> None:
        subprocess.run(["pbcopy"], input=text.encode(), check=False)

    def _clear_access_key_later(self) -> None:
        token = self.token

        def worker():
            time.sleep(60)
            current = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False).stdout
            if current == token:
                subprocess.run(["pbcopy"], input=b"", check=False)

        threading.Thread(target=worker, daemon=True).start()

    def _open_privacy_pane(self, pane: str, label: str) -> None:
        url = PRIVACY_PANES[pane]
        subprocess.Popen(["open", url])
        self._notify(f"Opened {label}. Grant only the access you want this connector to have.")

    def copy_permissions_guide(self, _):
        guide = (
            "Muse Mac Connector permissions guide\n\n"
            "Default features do not require Full Disk Access. macOS may request Files & Folders "
            "or Automation access as features are used. Full Disk Access, Accessibility, and Screen "
            "Recording are optional advanced permissions and should only be enabled when you want "
            "capabilities that need them. The connector cannot silently grant these permissions.\n\n"
            "Use Advanced Setup > Open Config File to choose which folders and actions Muse may request."
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
        self._ensure_services()
        self._refresh()
        self._notify("Connector started.")

    def stop_connector(self, _):
        self.tunnel.stop()
        self.agent.stop()
        self._refresh()
        self._notify("Connector stopped.")

    def connect_muse(self, _):
        self._ensure_services()
        for _ in range(30):
            if self.tunnel.public_url:
                break
            time.sleep(0.5)
        if not self.tunnel.public_url:
            self._notify("Tunnel is still starting. Try Connect to Muse again.")
            return
        self._copy(self._connection_prompt())
        webbrowser.open(MUSE_CHAT_URL)
        self._notify("Muse opened. Connection setup copied to the clipboard.")

    def copy_connection_prompt(self, _):
        self._ensure_services()
        if not self.tunnel.public_url:
            self._notify("No tunnel URL yet.")
            return
        self._copy(self._connection_prompt())
        self._notify("Muse connection setup copied.")

    def copy_access_key(self, _):
        self._copy(self.token)
        self._clear_access_key_later()
        self._notify("Access key copied for 60 seconds. Paste it only into Muse's secure field.")

    def restart_tunnel(self, _):
        self.tunnel.stop()
        if self.agent.is_running(self.token) and self.tunnel.start():
            self._notify("Tunnel restarting. A new Quick Tunnel URL will be created.")
        else:
            self._notify("Tunnel restart failed. Check the agent log.")
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

    @rumps.timer(5)
    def _tick(self, _):
        # Recover automatically if the local agent or cloudflared process exits.
        self._ensure_services()
        self._refresh()


def main():
    config.ensure_dirs()
    ConnectorApp().run()


if __name__ == "__main__":
    main()
