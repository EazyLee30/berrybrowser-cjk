#!/bin/sh
# Download the optional fonts. The default font (NotoSansSC-Regular.otf) is
# committed to the repo, so a fresh clone can already build build85.
#
#   sh fetch-fonts.sh            # both alternates
#   sh fetch-fonts.sh cjk        # full CJK, for build86
#   sh fetch-fonts.sh droid      # smallest (not recommended, see fonts/LICENSES.md)

set -e
cd "$(dirname "$0")/fonts"

get() { # url outfile
  [ -f "$2" ] && { echo "have $2"; return; }
  echo "fetching $2"
  curl -L# -o "$2" "$1"
}

fetch_all() {
  get "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" \
      NotoSansCJKsc-Regular.otf
  get "https://github.com/aosp-mirror/platform_frameworks_base/raw/master/data/fonts/DroidSansFallback.ttf" \
      DroidSansFallback.ttf
}

case "${1:-all}" in
  all)  fetch_all ;;
  cjk)  get "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" \
             NotoSansCJKsc-Regular.otf ;;
  droid) get "https://github.com/aosp-mirror/platform_frameworks_base/raw/master/data/fonts/DroidSansFallback.ttf" \
             DroidSansFallback.ttf ;;
  *)    echo "usage: $0 [all|cjk|droid]" >&2; exit 2 ;;
esac

echo
shasum -a 256 ./*.otf ./*.ttf 2>/dev/null || sha256sum ./*.otf ./*.ttf
echo
echo "expected (see fonts/LICENSES.md):"
echo "  faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9  NotoSansSC-Regular.otf"
echo "  2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b  NotoSansCJKsc-Regular.otf"
echo "  21b96a0377f067833a93af3082eb28d4ffab7a8cd46bfd513286f1d64b7b0949  DroidSansFallback.ttf"
