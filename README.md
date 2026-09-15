# Muse Mac Connector

An unofficial macOS menu-bar companion that gives Meta Muse a narrow, authenticated way to request user-approved actions on **your own Mac**.

> **Unofficial community project.** Not affiliated with, endorsed by, or maintained by Meta.

## Status

**Alpha / developer preview.** The connector works today. The current release uses a Cloudflare Quick Tunnel, so its public endpoint changes whenever the tunnel restarts. Choosing **Connect to Muse** copies the current endpoint automatically.

## Security-first defaults

- Local API binds only to `127.0.0.1:8899`.
- Remote access uses an outbound HTTPS Cloudflare tunnel.
- Every API request requires a randomly generated 256-bit access key.
- The key is stored in the current Mac user's Keychain when available.
- Every Mac action requires an on-device confirmation by default.
- File actions are limited to the current user's Downloads, Desktop, and Documents by default.
- **Pause Agent** immediately blocks new action requests.
- No folder monitoring, analytics, telemetry, project-owned backend, or background uploading.

## Menu-bar controls

- **Connect to Muse** — opens `https://muse.ai` and copies the current connection setup.
- **Copy Muse Access Key** — copies the Keychain-backed access key for 60 seconds.
- **Permissions & Capabilities** — explains optional macOS permissions and opens the relevant Privacy & Security pages.
- **Advanced Setup** — opens the per-user config file, scripts folder, or connector data folder.
- **Pause Agent** — blocks new action requests without closing the app.
- **Stop Connector** — closes the agent and tunnel.
- **Quit Connector** — cleanly stops all connector processes and exits.

## Current capabilities

- Run an Apple Shortcut.
- Move or copy files inside configured folders.
- Change a macOS `defaults` string value.
- Open an HTTP(S) URL.
- Run an executable script the user deliberately placed in the connector's scripts folder.

Nothing points at the original developer's files or accounts. Paths beginning with `~` resolve to the Mac user who installed the connector.

## Install from source

Requirements: macOS, Python 3, Homebrew, and an internet connection.

```bash
git clone https://github.com/dkm90x/muse-mac-connector.git
cd muse-mac-connector
./install.sh
./start-secure.sh
```

The source installer creates an isolated `.venv` and installs `cloudflared` through Homebrew if needed. A signed/notarized `.app`/`.dmg` is the next distribution milestone so ordinary users will not need Terminal.

## Connect Muse

1. Choose **Connect to Muse** from the menu-bar circle.
2. Paste the copied setup message into Muse.
3. If Muse asks for the credential through its secure field, choose **Copy Muse Access Key**.
4. Approve or deny each Mac action locally when prompted.

Never paste the access key into ordinary chat, an issue, a log, or source code.

## Permissions

The default connector does **not** need "full access" to the Mac. macOS may request access as a feature is used, and sensitive permissions must be granted explicitly by the Mac user.

The **Permissions & Capabilities** submenu links to Files & Folders, Full Disk Access, Automation, Accessibility, and Screen Recording settings. Full Disk Access, Accessibility, and Screen Recording are optional advanced permissions; enable them only when you intentionally add capabilities that require them.

With a source install, macOS may show the Python executable as the requesting process. A packaged app release will present the connector app itself.

## Configuration

Choose **Advanced Setup → Open Config File** to create/open:

`~/Library/Application Support/Muse Mac Connector/config.yaml`

The config controls the folders Muse may touch, the actions it may request, and which actions require confirmation. Changes apply after restarting the connector.

See [SECURITY.md](SECURITY.md) and [PRIVACY.md](PRIVACY.md) before widening access.
