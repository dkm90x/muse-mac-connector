# Stable VPS Relay

This optional transport gives Muse Mac Connector a permanent HTTPS endpoint while
keeping the Mac agent bound to `127.0.0.1:8899`.

## Data path

```text
Muse -> HTTPS -> Caddy on VPS -> 127.0.0.1:18899 on VPS
                                  ^
                                  |
                         reverse SSH tunnel
                                  |
                         Mac 127.0.0.1:8899
```

The VPS never needs the connector bearer token. Caddy forwards the caller's
Authorization header to the Mac agent, which remains the authentication boundary.

## Server bootstrap

Provision Ubuntu 24.04 LTS with the Mac's relay SSH public key, point a DNS A/AAAA
record at the VPS, then run as root:

```bash
export RELAY_PUBLIC_HOST=mac.example.com
export RELAY_SSH_PUBLIC_KEY='ssh-ed25519 AAAA... lifeos-relay'
./server/bootstrap-relay.sh
```

The bootstrap creates a `lifeos-relay` account constrained to remote forwarding,
limits the reverse listener to `127.0.0.1:18899`, enables Caddy, UFW,
unattended upgrades, and a 1 GiB swap file.

## Mac configuration

Add these keys to the connector config:

```yaml
transport_mode: vps_relay
relay_host: 203.0.113.10
relay_user: lifeos-relay
relay_ssh_port: 22
relay_remote_port: 18899
relay_public_url: https://mac.example.com
relay_identity_file: ~/.ssh/lifeos_linode_ed25519
```

Before enabling relay mode, connect to the VPS once from the Mac so its SSH host
key is pinned in `~/.ssh/known_hosts`. Relay mode uses
`StrictHostKeyChecking=yes` and will not silently trust a changed host key.

To return to the free Cloudflare transport:

```yaml
transport_mode: quick_tunnel
```
