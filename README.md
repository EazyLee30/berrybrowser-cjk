<p align="center">
  <img src="assets/banner.svg" alt="Berry Browser CJK — Chinese text on BlackBerry 10, without rebuilding Chromium" width="100%">
</p>

<p align="center">
  <a href="https://github.com/EazyLee30/berrybrowser-cjk/releases/latest"><img src="https://img.shields.io/github/v/release/EazyLee30/berrybrowser-cjk?color=4AFF7F&label=DOWNLOAD&style=for-the-badge" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/BERRY%20BROWSER-BUILD%20106-FFB000?style=for-the-badge" alt="Base: Berry Browser build 106">
  <img src="https://img.shields.io/badge/PLATFORM-QNX%208.0-9AA0A6?style=for-the-badge" alt="Platform: QNX 8.0">
  <img src="https://img.shields.io/badge/CPU-ARMv7-9AA0A6?style=for-the-badge" alt="CPU: ARMv7">
  <img src="https://img.shields.io/badge/ENGINE-BYTE%20IDENTICAL-4AFF7F?style=for-the-badge" alt="Engine binary is byte-identical to upstream">
  <img src="https://img.shields.io/badge/LICENSE-MIT-8957E5?style=for-the-badge" alt="MIT License">
</p>

<p align="center">
  <b>Reads Chinese. Cannot type Chinese.</b> The second half is a BB10 platform
  limitation, not a bug — <a href="#6-what-this-does-not-fix">§6</a> explains why no
  amount of repacking changes it.<br>
  <sub>能显示中文，不能输入中文。后者是 BB10 平台限制，<a href="#6-what-this-does-not-fix">见 §6</a>。</sub>
</p>

---

Berry Browser for BlackBerry 10 renders Latin text perfectly and every Chinese
codepoint as `□`. This fixes the `□`, by **repacking the official `.bar`** — the
engine binary is not recompiled and is byte-for-byte identical to the release it
came from.

```
$ python3 build_bar.py --release build106 --font fonts/NotoSansSC-Regular.otf --in-place
payload
  patched env-name    @ 0x001078  QNX_CA_BUNDLE -> QNX_FONT_DIR
  patched path-tmpl   @ 0x002384  %s/root_store.certs -> %s/fonts
  check    env-name reads back      ok
  check    path template reads back ok
  check    QNX_CA_BUNDLE gone       ok
  check    size unchanged           ok
  added  native/fonts/NotoSansSC-Regular.otf (8331336 bytes, sha256 faa6c9df652116dd…)
manifest ids
  in-place: reusing Package-Id testRel_erryShellV3d55e24f1 from the source
  package_version   3.0.2.107
```

## 1. Grab it

| Release asset | Size | Installs as |
|---|---|---|
| **`BerryBrowserCJK-build106-cjk107-inplace.bar`** | 65.1 MB | **in place** — upgrades the official Berry Browser, keeps your profile and cache |
| `BerryBrowserCJK-build106-cjk107-alongside.bar` | 65.1 MB | alongside — new `Package-Id`, for A/B against the official build |
| `BerryBrowserCJK-3.0.3-build85/86.bar` | 70.6 / 76.9 MB | alongside — the older build 84 base, kept for reproducing [v3.0.3](https://github.com/EazyLee30/berrybrowser-cjk/releases/tag/v3.0.3) |

**Take a build 106 one.** build 84 predates the Alt-key fix
([sw7ft/chromium-for-bb10#2](https://github.com/sw7ft/chromium-for-bb10/issues/2))
— on build 84 the Alt key never reaches the app at all, so anything involving Alt
cannot even be tested there.

```sh
# Sachesi / DDPB, or on-device:
cd /accounts/1000/shared/.installer
python3.2 installer.py /accounts/1000/shared/misc/BerryBrowserCJK-build106-cjk107-inplace.bar
```

Then read **[TEST.md](TEST.md)** — step 1 proves the diagnosis in about two
minutes **without installing anything**, and step 5 covers what to expect from
Alt and from Chinese input.

## 2. Why this needs no Chromium rebuild

Two independent things are wrong, both in
`src/content/shell/app/qnx_platform_stubs.cc`:

```cpp
// (a) no CJK-capable font is ever loaded
const char* font_dir = getenv("QNX_FONT_DIR");
if (!font_dir || !font_dir[0])
  font_dir = "/usr/fonts/font_repository";   // BB10 fonts: Latin, no CJK

// (b) there is no per-character fallback
bool GetFallbackFont(...)                    { return false; }
std::vector<Font> GetFallbackFonts(...)      { return {}; }
scoped_refptr<SimpleFontData> FontCache::PlatformFallbackFontForCharacter(...)
    { return FontCache::Get().GetLastResortFallbackFont(description); }
```

`QNX_FONT_DIR` *is* honoured — the string is right there in the shipped
`content_shell.exe` — but **nothing in the `.bar` ever sets it**. I grepped every
entry of the release: not in `bar-descriptor-v3.xml`, not in the `Entry-Point:`
environment prefix, not in the launcher. So the browser always loads
`/usr/fonts/font_repository`. Hence: English fine, Chinese tofu.

**The part that makes this fixable without a toolchain** is (b). With fontconfig
stubbed to `return false`, *no* font family ever matches, so every text run in
the browser already collapses onto a single typeface — the one Skia returns when
nothing matched. The browser is effectively single-font already. Ship **one**
font that contains both Latin and Simplified Chinese and both scripts render,
with zero code changes.

A rebuild is not an option regardless: the port's README requires Linux, the
proprietary **QNX SDP 8.0** at `/root/qnx800`, and a ~150–250 GB Chromium
checkout. It is also not needed.

Two constraints follow, and they matter:

* **The font directory must contain exactly one file.** Adding Noto *beside*
  the system fonts leaves the winner up to Skia's internal ordering, which will
  most likely still be a Latin-only face.
* **It must be its own subdirectory**, not the asset directory.
  `SkFontMgr_New_Custom_Directory()` reads every file in the directory and
  `SkTypeface_FreeType::MakeFromStream` copies each candidate into memory before
  parsing — pointing it at `native/` would make it try to slurp the 83 MB
  `content_shell.exe` on every launch.

`Noto Sans SC` Regular fits: 8.3 MB, 20 976 CJK + 6 582 CJK Ext-A glyphs *and*
full Latin, so nothing regresses.

## 3. How the `.bar` gets an *absolute* `QNX_FONT_DIR`

This is the one genuinely fiddly part, and it is why the obvious approach fails.
`<env var="QNX_FONT_DIR" value="app/native/fonts"/>` in `bar-descriptor.xml`
**does not work**: `main()` `chdir()`s off the asset directory into `$HOME` (or
`<sandbox>/data`) before `execv`-ing `content_shell`, so any relative path — from
`<env>` or from the `Entry-Point:` `VAR=value` prefix — resolves against the
wrong directory. And the correct absolute path embeds the `Package-Id`, so it
isn't knowable at pack time either.

The launcher already resolves its own directory from `/proc/self/exefile`, so the
fix belongs there. It already contains exactly one "build a path from the asset
dir and `setenv` it" block:

```c
char ca[2200];
snprintf(ca, sizeof(ca), "%s/root_store.certs", dir);
if (access(ca, R_OK) == 0)
  setenv("QNX_CA_BUNDLE", ca, 1);
```

`patch_launcher.py` retargets it with two in-place `.rodata` string
substitutions. Both only ever **shrink**, so nothing moves and no section grows:

```
0x001078  "QNX_CA_BUNDLE"       -> "QNX_FONT_DIR"    (14 -> 13 bytes)
0x002384  "%s/root_store.certs" -> "%s/fonts"        (20 ->  9 bytes)
```

Result: `QNX_FONT_DIR=<asset dir>/fonts` — absolute, correct on every BB10 model
and OS version, independent of cwd. If the directory is missing, `access()` fails,
the variable is simply not set, and you fall back to today's behaviour. The
failure mode is the status quo, never a crash.

**What this gives up:** `QNX_CA_BUNDLE` is no longer exported. Verified safe for
this build — the string occurs exactly once inside `content_shell.exe`, in a
child-process environment forwarding list
(`patches/mp-gpu-navigation.patch`, `kForwardEnv`); the binary never reads it as
a certificate path; HTTPS already runs with `--ignore-certificate-errors`; and
the port's own README states there is no root CA store on the device.
`root_store.certs` is still shipped, untouched.

The equivalent change **at source** — 6 lines in `launcher.c` plus one `<asset>`,
which is what actually belongs in `berry-v3` — is in
[`upstream/launcher-fonts.patch`](upstream/launcher-fonts.patch).

## 4. Verify before you sideload

`verify_bar.py` is not decoration; it is the reason to trust the output.

```
$ python3 verify_bar.py out/BerryBrowserCJK-build106-cjk107-inplace.bar \
    --src work/BerryBrowserV3-3.0.2-build106.bar --expect-in-place
[  ok  ] every SHA-512 digest matches
[  ok  ] launcher exports QNX_FONT_DIR
[  ok  ] launcher builds it from the asset dir  — format string '%s/fonts' present
[  ok  ] native/content_shell.exe byte-identical to source
[  ok  ] Package-Id matches the source (real in-place upgrade)
  ours=testRel_erryShellV3d55e24f1  source=testRel_erryShellV3d55e24f1
[  ok  ] Package-Version-Id differs from the source (BB10 sees an upgrade)
[  ok  ] exactly one font shipped  — ['native/fonts/NotoSansSC-Regular.otf']
[  ok  ] font covers CJK Unified Ideographs  — 20976 CJK glyphs
[  ok  ] font covers CJK Ext A  — 6582 Ext-A glyphs
[  ok  ] font is not a variable font (old Skia/FreeType on QNX)
  ...
all checks passed — safe to sideload
```

It proves the engine binary is untouched, every digest matches, the launcher
patch reads back correctly, the font's `cmap` actually covers the CJK + Latin +
full-width-punctuation sample, and the package ids are the shape BB10 expects.

## 5. Build it yourself

```bash
python3 build_bar.py --font fonts/NotoSansSC-Regular.otf --in-place
python3 verify_bar.py out/BerryBrowserCJK-build106-cjk107-inplace.bar \
  --src work/BerryBrowserV3-3.0.2-build106.bar --expect-in-place
```

`--release build106` (default) or `build84`. `--in-place` reuses the source's
`Package-Id` byte for byte so BB10 treats it as an **upgrade** and `appdata`
survives; without it you get a new `Package-Id` and the two apps coexist.

## 6. What this does **not** fix

**You can read Chinese in Berry Browser. You cannot type Chinese in it.** Not a
font problem, and no repack touches it.

* **Chinese input needs platform integration Berry Browser does not have.** BB10's
  Pinyin IME and its candidate window come from the platform IME service.
  Cascades apps get an input context from the Qt QNX platform plugin. Berry
  Browser is a Cascades-less `systemChrome=none` native `Qnx/Elf` BAR driving
  libscreen through its own `qnx_screen` Ozone backend — nothing for the platform
  IME to attach to.
* **The port adds none either.** `ui::KeyboardHook::CreateModifierKeyboardHook()`
  returns `nullptr`, and the `ui::InitializeInputMethod()` in
  `patches/qnx-port.patch` is only a `write(2, "QNX:BMRI:8 InputMethod\n", ...)`
  trace marker.
* **"Alt key fixed" upstream is about Alt as a *modifier*** (Alt+Left and
  friends), not the OS input-method toggle. Do not read it as IME support.
* **The clipboard workaround is closed too.** `qnx_platform_stubs.cc` has
  `Clipboard* ui::Clipboard::Create() { return new ClipboardNonBacked; }` — an
  in-process clipboard with no system backend — so you cannot compose Chinese in
  a Cascades app and paste it in.
* **Emoji stay `□`.** No font here has colour emoji and BB10's own fonts have
  none either, so this is not a regression.
* **One weight.** Chromium synthesises bold. Shipping Bold/Italic would mean more
  than one file in the font directory, which breaks §2's single-font property.
* **`<pre>` blocks render proportional**, because without per-character fallback
  there is no way to substitute a monospace face for some characters and not
  others.

**The realistic next increment is a real QNX clipboard backend, not an IME
client** — a much smaller job, self-contained (it does not touch Blink or the
renderer at all), and it would make text composed anywhere in BB10 pasteable
into the browser. It still needs a rebuild, so the real blocker is unchanged:
the proprietary **QNX SDP 8.0**. Nothing engine-side — mine, upstream's, or
anyone's — can be compiled without it.

## 7. Repo map

| | |
|---|---|
| [`patch_launcher.py`](patch_launcher.py) | the two-string patch, standalone and auditable |
| [`build_bar.py`](build_bar.py) | repack: patch launcher, add font, regenerate manifest + ids |
| [`verify_bar.py`](verify_bar.py) | 25 pre-sideload checks |
| [`TEST.md`](TEST.md) | device procedure, starting with a no-install check |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | marker-file A/B table, log greps, per-symptom steps |
| [`on-device-fix.sh`](on-device-fix.sh) | contingency if the installer didn't create `fonts/` |
| [`fetch-fonts.sh`](fetch-fonts.sh) | optional fonts (the default one is committed) |
| [`upstream/`](upstream/launcher-fonts.patch) | the source-level fix for `berry-v3` |
| [`fonts/`](fonts/LICENSES.md) | candidate fonts + licences |

## 8. Credits

* **[sw7ft](https://github.com/sw7ft)** — [chromium-for-bb10](https://github.com/sw7ft/chromium-for-bb10)
  is the whole reason this is possible: an actual Chromium port for QNX, plus
  [sw7ft/berry-browser](https://github.com/sw7ft/berry-browser) for the builds.
  None of their code is redistributed here; this only repackages their published
  `.bar`.
* **[Noto](https://github.com/notofonts/noto-cjk)** — Noto Sans SC, SIL OFL 1.1.
* [upstream issue #6](https://github.com/sw7ft/chromium-for-bb10/issues/6) — where
  the source-level fix was filed.

<p align="center">
  <sub>Not affiliated with BlackBerry Limited. Long live BlackBerry.</sub>
</p>
