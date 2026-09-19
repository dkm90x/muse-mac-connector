#!/usr/bin/env bash
set -euo pipefail

: "${RELAY_PUBLIC_HOST:?Set RELAY_PUBLIC_HOST, e.g. mac.example.com}"
: "${RELAY_SSH_PUBLIC_KEY:?Set RELAY_SSH_PUBLIC_KEY to the Mac relay public key}"

RELAY_USER="${RELAY_USER:-lifeos-relay}"
RELAY_PORT="${RELAY_PORT:-18899}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y caddy ufw unattended-upgrades

if ! id -u "${RELAY_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${RELAY_USER}"
fi

RELAY_HOME="$(getent passwd "${RELAY_USER}" | cut -d: -f6)"
install -d -m 700 -o "${RELAY_USER}" -g "${RELAY_USER}" "${RELAY_HOME}/.ssh"
printf '%s\n' "${RELAY_SSH_PUBLIC_KEY}" > "${RELAY_HOME}/.ssh/authorized_keys"
chown "${RELAY_USER}:${RELAY_USER}" "${RELAY_HOME}/.ssh/authorized_keys"
chmod 600 "${RELAY_HOME}/.ssh/authorized_keys"

cat > /etc/ssh/sshd_config.d/90-lifeos-relay.conf <<EOF
PermitRootLogin prohibit-password
PasswordAuthentication no

Match User ${RELAY_USER}
    AuthenticationMethods publickey
    PasswordAuthentication no
    AllowTcpForwarding remote
    GatewayPorts no
    PermitListen 127.0.0.1:${RELAY_PORT}
    X11Forwarding no
    AllowAgentForwarding no
    PermitTTY no
EOF

sshd -t
systemctl reload ssh

cat > /etc/caddy/Caddyfile <<EOF
${RELAY_PUBLIC_HOST} {
    encode zstd gzip
    reverse_proxy 127.0.0.1:${RELAY_PORT}

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
    }
}
EOF

caddy validate --config /etc/caddy/Caddyfile
systemctl enable --now caddy

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

if ! swapon --show=NAME --noheadings | grep -q '^/swapfile$'; then
  if [[ ! -f /swapfile ]]; then
    fallocate -l 1G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

systemctl enable --now unattended-upgrades
echo "Relay host prepared: https://${RELAY_PUBLIC_HOST}"
echo "Reverse SSH target: 127.0.0.1:${RELAY_PORT}"
