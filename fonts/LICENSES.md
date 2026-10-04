# Font provenance and licences

All fonts here are SIL Open Font License 1.1. Keep the licence file that ships
with whichever font you redistribute inside the `.bar`.

| File | Size | Family | Glyphs | CJK | Ext-A | Latin | Notes |
|---|---|---|---|---|---|---|---|
| `NotoSansSC-Regular.otf` | 8.3 MB | Noto Sans SC | 30 890 | 20 976 | 6 582 | yes | **Default.** Subset OTF, SC only. Best size/quality trade-off. |
| `NotoSansCJKsc-Regular.otf` | 16.4 MB | Noto Sans CJK SC | 44 810 | 20 976 | 6 582 | yes | Full CJK font. Identical CJK coverage, more non-CJK scripts (JP/KR/TC forms), 8 MB bigger. Use if you read Japanese/Korean too. |
| `DroidSansFallback.ttf` | 3.4 MB | Droid Sans Fallback | 33 275 | 20 902 | 2 | partial | Smallest. TrueType instead of CFF. **Missing U+2014 (—), U+2026 (…), U+20AC (€)** — you will see boxes on ordinary pages. Not recommended. |

Downloads: `NotoSansSC-Regular.otf` is committed to this repo. The other two are
not (20 MB) — `sh fetch-fonts.sh` gets them:

```bash
# default (already committed)
curl -L -o fonts/NotoSansSC-Regular.otf \
  https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf

# full CJK
curl -L -o fonts/NotoSansCJKsc-Regular.otf \
  https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf

# smallest (not recommended)
curl -L -o fonts/DroidSansFallback.ttf \
  https://github.com/aosp-mirror/platform_frameworks_base/raw/master/data/fonts/DroidSansFallback.ttf
```

SHA-256 of the copies in this directory:

```
faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9  NotoSansSC-Regular.otf
2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b  NotoSansCJKsc-Regular.otf
21b96a0377f067833a93af3082eb28d4ffab7a8cd46bfd513286f1d64b7b0949  DroidSansFallback.ttf
```

`NotoSansSC[wght].ttf` (the Google Fonts variable font) was downloaded and then
**deleted on purpose**: it carries an `fvar` table, and the FreeType build this
port links against is old enough that variable-font handling is not worth
trusting on a 32-bit device. `verify_bar.py` fails the build if an `fvar` table
shows up in the chosen font.

## Why one font must carry both scripts

The QNX port has no per-character fallback: Blink's
`FontCache::PlatformFallbackFontForCharacter()` returns
`GetLastResortFallbackFont()`, and with fontconfig stubbed out no font family
ever matches, so *every* text run in the browser resolves to the same single
typeface. That means:

* one font in the font directory ⇒ all Latin **and** all Chinese come from it;
* several fonts in the directory ⇒ whichever one happens to be index 0 wins,
  and you are back to boxes for whichever script it lacks.

This is why `verify_bar.py` fails if the `.bar` ships anything other than
exactly one font file, and why the font directory is its own subdirectory rather
than the asset directory itself (see README, "Why a dedicated subdirectory").
