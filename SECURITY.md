# Security

Muse Mac Connector exposes capabilities on a user's Mac, so security defaults are intentionally conservative.

## Security model

- The local service binds to `127.0.0.1` only.
- Remote access travels through an outbound Cloudflare tunnel.
- Every API request requires a randomly generated 256-bit bearer key.
- The key is stored in macOS Keychain when available, with a mode-0600 local fallback only if Keychain is unavailable.
- Restricted Mode limits filesystem operations to configured roots and uses conservative command parsing.
- Full Computer Mode is an explicit local opt-in that removes connector path/command fences and grants user-level authority; macOS permissions and filesystem protections still apply.
- Obvious destructive, privileged, and credential-sensitive Full Mode operations require local confirmation. Restricted Mode actions use their configured confirmation policy.
- **Pause Agent** blocks new `/task` requests immediately.
- Request bodies are size-limited and results are kept only in bounded in-memory storage.

## Secrets

Never commit access keys, tunnel credentials, `.env` files, private keys, or local configuration containing secrets. The repository's `.gitignore` covers common secret-bearing files, but contributors are responsible for reviewing changes before committing.

## Reporting a vulnerability

Do not post credentials or exploit details in a public issue. Contact the repository owner privately through GitHub and include the affected version, reproduction steps, and impact.

## Scope note

This is an alpha developer preview. It has not undergone an independent security audit. Full Computer Mode is intentionally powerful: its command approval detector is a safeguard for obvious visible risk, not a perfect analysis of arbitrary scripts. Enable it only for a trusted connected agent. See [FULL_COMPUTER_MODE.md](FULL_COMPUTER_MODE.md).
