## 0.4.3 — 2026-09-15

- Added a connector behavior contract for AI clients.
- `GET /capabilities` now includes usage policy alongside action schemas.
- AI clients are told to use advertised connector actions instead of requesting Terminal installers or setup workarounds.
- Missing capabilities must be reported explicitly rather than replaced with improvised access methods.

# Changelog

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
