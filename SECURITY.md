# Security

Muse Mac Connector exposes capabilities on a user's Mac, so security defaults are intentionally conservative.

## Security model

- The local service binds to `127.0.0.1` only.
- Remote access travels through an outbound Cloudflare tunnel.
- Every API request requires a randomly generated 256-bit bearer key.
- The key is stored in macOS Keychain when available, with a mode-0600 local fallback only if Keychain is unavailable.
- Filesystem operations are limited to configured roots.
- Requested actions require local confirmation by default.
- **Pause Agent** blocks new `/task` requests immediately.
- Request bodies are size-limited and results are kept only in bounded in-memory storage.

## Secrets

Never commit access keys, tunnel credentials, `.env` files, private keys, or local configuration containing secrets. The repository's `.gitignore` covers common secret-bearing files, but contributors are responsible for reviewing changes before committing.

## Reporting a vulnerability

Do not post credentials or exploit details in a public issue. Contact the repository owner privately through GitHub and include the affected version, reproduction steps, and impact.

## Scope note

This is an alpha developer preview. It has not undergone an independent security audit. Do not expose capabilities you would not be comfortable approving locally.
