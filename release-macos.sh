#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/dist/Muse Mac Connector.app"
STAGE="$ROOT/dist/dmg-stage"
DMG="$ROOT/dist/Muse-Mac-Connector.dmg"
IDENTITY="${MUSE_SIGN_IDENTITY:-}"
NOTARY_PROFILE="${MUSE_NOTARY_PROFILE:-muse-mac-connector}"

if [[ -z "$IDENTITY" ]]; then
  IDENTITY="$(security find-identity -v -p codesigning | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1)"
fi
if [[ -z "$IDENTITY" ]]; then
  echo "No Developer ID Application certificate found." >&2
  exit 2
fi

"$ROOT/build-app.sh"
echo "Signing app with: $IDENTITY"
find "$APP/Contents" -type f -perm -111 -print0 | while IFS= read -r -d '' FILE; do
  if file "$FILE" | grep -q 'Mach-O'; then
    codesign --force --options runtime --timestamp --sign "$IDENTITY" "$FILE"
  fi
done

find "$APP/Contents/Frameworks" -type d \( -name '*.framework' -o -name '*.app' \) -depth -print0 2>/dev/null | while IFS= read -r -d '' BUNDLE; do
  codesign --force --options runtime --timestamp --sign "$IDENTITY" "$BUNDLE"
done

codesign --force --options runtime --timestamp --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"
spctl --assess --type execute --verbose=2 "$APP"

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Muse Mac Connector" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
echo "Submitting DMG to Apple notarization service..."
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait

xcrun stapler staple "$APP"
xcrun stapler staple "$DMG"
xcrun stapler validate "$APP"
xcrun stapler validate "$DMG"
spctl --assess --type execute --verbose=2 "$APP"

echo "Release ready: $DMG"
