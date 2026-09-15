# Privacy

Muse Mac Connector is designed to avoid collecting data of its own.

## Connector behavior

- No analytics or telemetry are built into this repository.
- The connector does not watch folders or copy files in the background.
- It does not operate a project-owned backend or database.
- The local service listens only on `127.0.0.1` and is reached remotely through the user-started Cloudflare tunnel.
- File and action requests are initiated through the connected Muse session and are subject to the connector's allowlist and local confirmation settings.

## Access key

The bearer access key is generated locally. The connector stores it in macOS Keychain when available. When the user explicitly copies it to the clipboard, the connector clears it after 60 seconds if the clipboard still contains that key.

## Third parties

Using Meta Muse and Cloudflare means traffic may be processed by those services under their own terms and privacy policies. This project does not control their data practices.
