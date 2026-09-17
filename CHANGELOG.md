# Changelog

## 0.5.0-alpha — 2026-09-16

- Added a shared machine-readable capability registry with 11 packs, 25 operational actions, and a consent-gated Full Mode access action.
- Defined Full Computer Mode as user-level Mac authority after explicit local approval: no connector-imposed folder, app, or normal command-workflow fences.
- Added `access.enable_full` so Muse can request Full Mode from Restricted Mode; approval updates the running helper immediately without restart.
- Added file read/write/list/mkdir/trash, guarded developer command execution, process supervision, app launch, clipboard, screen capture, and Accessibility UI primitives.
- Added `muse-mac capabilities`, `muse-mac enable all`, and `muse-mac doctor`.
- Added first-run plain-language onboarding and a permanent **How to Use — Easy Steps** menu.
- Added **Capability Index** and **Enable Full Computer Mode** menu controls.
- Opening the already-running app now refreshes the Quick Tunnel and automatically copies the new Muse connection setup.
- Kept destructive file trash and settings changes behind local confirmation in Full Computer Mode.
- Verified the packaged app on macOS with the operator/security test suite and live Quick Tunnel health/action checks.

## 0.4.3 — 2026-09-15

- Added a connector behavior contract for AI clients.
- `GET /capabilities` now includes usage policy alongside action schemas.
- AI clients are told to use advertised connector actions instead of requesting Terminal installers or setup workarounds.
- Missing capabilities must be reported explicitly rather than replaced with improvised access methods.

## v0.4.2 — 2026-09-15

- Fixed standalone `.app` helper startup.
- Added packaged-agent self-test support.
- Require real agent health before reporting the connector as running.
- Bundled Python runtime and `cloudflared` for click-to-launch builds.
- Added automatic service recovery.
- Added MIT licensing and public-project documentation.

## v0.4.1

- Added tunnel restart controls and automatic recovery after tunnel/process failure.
- Expanded menu-bar permission and advanced-setup controls.

## v0.4.0

- First cleaned public-ready alpha architecture.
- Keychain-backed access key, localhost API, Cloudflare Quick Tunnel, guarded actions, security tests.
