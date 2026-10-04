# Berry Browser CJK — Chinese text on BlackBerry 10, without rebuilding Chromium

Fixes the "英文正常，中文全是 □□□□" problem in
[sw7ft/chromium-for-bb10](https://github.com/sw7ft/chromium-for-bb10) Berry Browser
by **repacking the official `.bar`**. The 96 MB engine binary is not recompiled
and is byte-for-byte identical to the release.

```
out/BerryBrowserCJK-3.0.3-build85.bar   70.6 MB   ← default (Noto Sans SC, 8.3 MB)
out/BerryBrowserCJK-3.0.3-build86.bar   76.9 MB   ← full CJK (Noto Sans CJK SC, 16.4 MB)
```

Both install **alongside** the official Berry Browser (different `Package-Id`),
so you can A/B them and delete them again without touching the official app.

---

## 1. The diagnosis is right, and it is confirmed in the shipped binary

Both halves of the report check out against `native/content_shell.exe` from
`releases/BerryBrowserV3-3.0.2-build84.bar`:

```console
$ strings -a content_shell.exe | grep -E 'QNX_FONT_DIR|font_repository'
QNX_FONT_DIR
/usr/fonts/font_repository
```

and in [`qnx_platform_stubs.cc`](https://github.com/sw7ft/chromium-for-bb10/blob/main/src/content/shell/app/qnx_platform_stubs.cc):

```cpp
// gfx: character-level fallback is stubbed out
bool GetFallbackFont(...)  { return false; }
std::vector<Font> GetFallbackFonts(...) { return {}; }

// Blink: never searches for a font that HAS the character
scoped_refptr<SimpleFontData> FontCache::PlatformFallbackFontForCharacter(...)
    { return FontCache::Get().GetLastResortFallbackFont(description); }

// Skia: one directory, no fontconfig
sk_sp<SkFontMgr> CreateDefaultSkFontMgr() {
  const char* font_dir = getenv("QNX_FONT_DIR");
  if (!font_dir || !font_dir[0]) font_dir = "/usr/fonts/font_repository";
  ...
}
```

**Nothing in the `.bar` ever sets `QNX_FONT_DIR`** — I grepped every entry in the
release: it is not in `bar-descriptor-v3.xml`, not in the `Entry-Point:`
environment prefix (which only carries `LD_LIBRARY_PATH`), and the launcher does
not set it. So the browser always loads `/usr/fonts/font_repository`, whose
BB10 fonts carry Latin but not Simplified Chinese. Hence: English fine, Chinese
tofu.

## 2. Why you do **not** need to fork and rebuild

The plan in the report was: bundle a CJK font, point `QNX_FONT_DIR` at it, then
*also* fix `PlatformFallbackFontForCharacter()` by recompiling. Step 3 is where
it falls apart, and it is also the step that costs everything:

* **It needs a toolchain you cannot get.** The port's own README requires Linux
  + **QNX SDP 8.0** at `/root/qnx800` (proprietary, license-gated from BlackBerry/QNX)
  + Clang/LLD 17 + `patchelf`, and a Chromium checkout of ~150–250 GB at commit
  `ad76543128c`. Hours-to-days per build. Note also that the live code is the
  `berry-v3` branch; `main` is only a docs/patch/binary snapshot.
* **It is not needed.** With fontconfig stubbed to `return false`, *no* font
  family ever matches, so every text run in the browser collapses onto the same
  single typeface — the one Skia hands back when nothing matched. The browser is
  already effectively single-font. If that one font contains both Latin and
  Simplified Chinese, **Chinese renders correctly with zero code changes.**

That is the whole trick: make the single font a bilingual one.

## 3. Why a dedicated subdirectory, and why only one font

* **Only one font.** The chosen typeface is "whatever Skia returns when no
  family matched". Adding Noto *alongside* DejaVu/Verdana would leave the winner
  up to Skia's internal ordering — most likely still a Latin-only face, and you
  would be back to boxes. Pointing `QNX_FONT_DIR` at a directory containing
  exactly one bilingual font makes the outcome deterministic.
* **A subdirectory, not the asset directory itself.** `SkFontMgr_New_Custom_Directory()`
  reads *every* file in the directory, and `SkTypeface_FreeType::MakeFromStream`
  copies each candidate into memory before parsing. Pointing it at the app's
  `native/` dir would make it try to slurp the 96 MB `content_shell.exe` on every
  launch. `native/fonts/` holds one 8 MB file and nothing else.
* Side effect worth knowing: because there is no per-character fallback, a
  `<pre>`/code block will render in Noto Sans SC (proportional) rather than a
  monospace face. Cosmetic, and unavoidable without step 3.

## 4. How the `.bar` gets an *absolute* `QNX_FONT_DIR`

This is the one genuinely fiddly part, and it is why the previous plan's
`<env var="QNX_FONT_DIR" value="app/native/fonts"/>` would not have worked:

* The launcher resolves its own directory from `/proc/self/exefile` and then
  **`chdir()`s away** into `$HOME` (or `<sandbox>/data`) before `execv`-ing
  `content_shell`. So any *relative* font path — from `<env>` or from the
  `Entry-Point:` `VAR=value` prefix — is resolved against the wrong directory.
* The absolute path is only knowable at run time, because it embeds the
  `Package-Id`.

So the font directory is computed **by the launcher, at launch**. The launcher
already contains exactly one "build a path from the asset dir and export it"
block:

```c
char ca[2200];
snprintf(ca, sizeof(ca), "%s/root_store.certs", dir);
if (access(ca, R_OK) == 0)
  setenv("QNX_CA_BUNDLE", ca, 1);
```

`patch_launcher.py` retargets it with two in-place `.rodata` string
substitutions. Both only ever **shrink**, so nothing moves and no section grows:

```
0x000cf0  "QNX_CA_BUNDLE"        -> "QNX_FONT_DIR"    (14 -> 13 bytes)
0x001e50  "%s/root_store.certs"  -> "%s/fonts"        (20 ->  9 bytes)
```

Result: `QNX_FONT_DIR=<asset dir>/fonts`, absolute, correct on every BB10 model
and OS version, independent of cwd. If the directory is missing, `access()`
fails, the variable is simply not set, and you fall back to today's behaviour —
the failure mode is the status quo, never a crash.

**What this gives up:** `QNX_CA_BUNDLE` is no longer exported. Verified safe for
this build — the string occurs exactly once inside `content_shell.exe`, in a
child-process environment forwarding list
(`patches/mp-gpu-navigation.patch`, `kForwardEnv`); the binary never reads it as
a certificate path; HTTPS already runs with `--ignore-certificate-errors`; and
the port's own README states there is no root CA store on the device.

`root_store.certs` is still shipped in the `.bar`, untouched.

## 5. Layout

```
patch_launcher.py        the 2-string patch, standalone + auditable
build_bar.py             repack: patch launcher, add font, new manifest + ids
verify_bar.py            25 checks; run this before every sideload
on-device-fix.sh         contingency if the installer didn't create fonts/
fetch-fonts.sh           optional fonts (the default one is committed)
upstream/                launcher-fonts.patch: the source-level fix for sw7ft,
                         i.e. what belongs in berry-v3 rather than in a repack
fonts/                   the candidate fonts + LICENSES.md
work/                    scratch: the 61 MB upstream .bar, downloaded on demand
out/                     the built .bar files
```

The 61 MB upstream `.bar` and the ~160 MB of built `.bar` files are **not** in
git — the former is downloaded by `build_bar.py`, the latter are attached to the
GitHub Release.

## 6. Build / verify / install

```bash
# 1. build — downloads the upstream release on first run
python3 build_bar.py --font fonts/NotoSansSC-Regular.otf

# 2. verify — 25 checks, all must pass
python3 verify_bar.py out/BerryBrowserCJK-3.0.3-build85.bar

# 3. sideload out/BerryBrowserCJK-3.0.3-build85.bar (Sachesi / DDPB / device installer)
```

Then follow **[TEST.md](TEST.md)** — start with step 1 there, which proves the
diagnosis in about two minutes **without installing anything**.

Switching fonts / naming is all flags:

```bash
sh fetch-fonts.sh cjk     # the full CJK font is not committed
python3 build_bar.py --font fonts/NotoSansCJKsc-Regular.otf \
                     --version 3.0.3 --build 86 \
                     --package com.sw7ft.BerryShellV3CJKFull \
                     --name "Berry Browser CJK+"
```

Always bump `--package` (or at least `--build`) when rebuilding: BB10 silently
refuses to overwrite an installed package whose `Package-Id` it already knows.

## 7. Known limits

* **Emoji stay boxes.** No font shipped here has colour emoji, and BB10's own
  fonts have none either, so this is not a regression. A monochrome
  `NotoEmoji` (CBDT) would probably render via Skia, but that is untested —
  don't trust it without trying.
* **One weight, one style.** Only Regular exists. Chromium will synthesise bold
  by emboldening. Shipping Bold/Italic would mean more than one file in the
  directory, which breaks the "single font wins" property described in §3.
* **Taiwan / Hong Kong / Japanese / Korean** want the full CJK font
  (`build86`, Noto Sans CJK SC) rather than the SC subset.
* **Not tested on hardware.** Everything above is verified statically — string
  offsets, SHA-512 digests, byte-identity of the engine binary, font cmap
  coverage, BAR manifest shape. The one thing I cannot do from a Mac is run it
  on a Q20, which is exactly why `TEST.md` starts with a no-install check.
