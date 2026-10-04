#!/bin/sh
# Contingency: make QNX_FONT_DIR work even if the BB10 installer did NOT create
# app/native/fonts/ inside the installed app.
#
# Run this over SSH / Term49 on the phone as the app's own user. It is a no-op
# when the directory already exists.
#
#   sh on-device-fix.sh <package-id>
#
# <package-id> is the Package-Id from META-INF/MANIFEST.MF of the .bar you
# installed, e.g. testQWe_Ss5gbzxAiMRN9hW3S50  (BerryBrowserCJK-3.0.3-build85.bar)
#
# For the official build (no CJK patch) pass testRel_erryShellV3d55e24f1.

set -e

PKG="${1:-}"
if [ -z "$PKG" ]; then
  echo "usage: $0 <package-id>" >&2
  exit 2
fi

FONT="${2:-/accounts/1000/shared/misc/NotoSansSC-Regular.otf}"

for base in "/accounts/1000/appdata/$PKG/app/native" "/apps/$PKG/native"; do
  if [ -d "$base" ]; then
    NATIVE="$base"
    break
  fi
done

if [ -z "${NATIVE:-}" ]; then
  echo "could not locate the app's native asset dir for $PKG" >&2
  echo "looked in:" >&2
  echo "  /accounts/1000/appdata/$PKG/app/native" >&2
  echo "  /apps/$PKG/native" >&2
  exit 1
fi

echo "native asset dir: $NATIVE"

if [ ! -f "$FONT" ]; then
  echo "font not found: $FONT" >&2
  echo "copy NotoSansSC-Regular.otf there first, e.g." >&2
  echo "  scp fonts/NotoSansSC-Regular.otf \\" >&2
  echo "      devuser@<phone>:/accounts/1000/shared/misc/" >&2
  exit 1
fi

mkdir -p "$NATIVE/fonts"
cp -f "$FONT" "$NATIVE/fonts/NotoSansSC-Regular.otf"

echo "installed: $NATIVE/fonts/NotoSansSC-Regular.otf"
ls -l "$NATIVE/fonts/"

cat <<EOF

Done. Relaunch the browser from the home screen.

If it still shows boxes, check the log -- the launcher prints the asset dir it
resolved from /proc/self/exefile:

  tail -40 /accounts/1000/shared/misc/berry-kbd.log | grep 'app dir'

QNX_FONT_DIR will be "<that path>/fonts".
EOF
