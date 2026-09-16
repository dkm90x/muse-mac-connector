#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -x "$ROOT/.venv/bin/python3" ]]; then
  ./install.sh
fi
"$ROOT/.venv/bin/python3" -m pip install --quiet -r build-requirements.txt

rm -rf build dist assets/AppIcon.iconset assets/AppIcon.icns
mkdir -p assets/AppIcon.iconset /tmp/muse-mac-connector-icon
qlmanage -t -s 1024 -o /tmp/muse-mac-connector-icon assets/AppIcon.svg >/dev/null 2>&1
SRC="/tmp/muse-mac-connector-icon/AppIcon.svg.png"

for SIZE in 16 32 128 256 512; do
  sips -z "$SIZE" "$SIZE" "$SRC" --out "assets/AppIcon.iconset/icon_${SIZE}x${SIZE}.png" >/dev/null
  DOUBLE=$((SIZE * 2))
  sips -z "$DOUBLE" "$DOUBLE" "$SRC" --out "assets/AppIcon.iconset/icon_${SIZE}x${SIZE}@2x.png" >/dev/null
done
iconutil -c icns assets/AppIcon.iconset -o assets/AppIcon.icns

"$ROOT/.venv/bin/python3" setup.py py2app >/dev/null
APP="$ROOT/dist/Muse Mac Connector.app"
mkdir -p "$APP/Contents/Resources"
CLOUDFLARED="$(command -v cloudflared || true)"
if [[ -z "$CLOUDFLARED" ]]; then
  for CANDIDATE in /opt/homebrew/bin/cloudflared /usr/local/bin/cloudflared; do
    [[ -x "$CANDIDATE" ]] && CLOUDFLARED="$CANDIDATE" && break
  done
fi
if [[ -z "$CLOUDFLARED" ]]; then
  echo "cloudflared is required to build the standalone app." >&2
  exit 1
fi
cp "$CLOUDFLARED" "$APP/Contents/Resources/cloudflared"
chmod +x "$APP/Contents/Resources/cloudflared"

# Local builds use ad-hoc signing. Release builds should use Developer ID + notarization.
codesign --force --deep --sign - "$APP"
echo "Built: $APP"
