#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Muse Mac Connector currently supports macOS only." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required." >&2
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required for the source install: https://brew.sh" >&2
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Installing cloudflared..."
  brew install cloudflared
fi

python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python3" -m pip install --quiet --upgrade pip
"$ROOT/.venv/bin/python3" -m pip install --quiet -r "$ROOT/agent-requirements.txt" -r "$ROOT/requirements.txt"

echo "Installed. Start with: $ROOT/start-secure.sh"
