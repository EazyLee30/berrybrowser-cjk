<p align="center">
  <img src="assets/banner.svg" alt="Berry Browser CJK" width="420">
</p>

<p align="center">
  <a href="README.md">README</a> ·
  <a href="TEST.md">TEST</a> ·
  <a href="TROUBLESHOOTING.md">TROUBLESHOOTING</a>
</p>

---


Do these in order. **Step 1 installs nothing** and proves (or kills) the whole
diagnosis in about two minutes, so never skip it.

Throughout: `berry-kbd.log` is the browser's own log, readable from a PC over
USB/SSH as `devuser`:

```bash
tail -f /accounts/1000/shared/misc/berry-kbd.log
```

---

## Step 0 — confirm the symptom

Open a page that is mostly Chinese text and no images, e.g.

```
https://zh.wikipedia.org/wiki/黑莓
```

You should see `□□□□` where the Chinese should be, with Latin (the URL bar, the
`zh.wikipedia.org` domain) rendering fine. Keep that page open for comparison.

---

## Step 1 — prove it without installing anything (recommended)

Copy the font to a world-readable shared folder and launch the existing browser
binary by hand with `QNX_FONT_DIR` pointing at it.

**On the PC:**

```bash
scp fonts/NotoSansSC-Regular.otf \
    devuser@169.254.0.1:/accounts/1000/shared/misc/
```

**On the phone** (Momentics terminal, or `ssh devuser@169.254.0.1`):

```sh
cd /accounts/1000/appdata/testRel_erryShellV3d55e24f1/app/native

# Sanity: the engine really does honour the variable.
strings content_shell.exe | grep QNX_FONT_DIR

# Run it. --single-process mirrors what the launcher does.
QNX_FONT_DIR=/accounts/1000/shared/misc \
LD_LIBRARY_PATH=. \
./content_shell.exe --no-sandbox --no-zygote --single-process \
  --disable-gpu --ozone-platform=qnx_screen \
  'https://zh.wikipedia.org/wiki/黑莓'
```

(The exact app dir may be `/apps/<package-id>/native` instead — `ls
/accounts/1000/appdata/` and `/apps/` will tell you.)

### Reading the result

| What you see | Meaning | Go to |
|---|---|---|
| Chinese renders, Latin still fine | diagnosis confirmed, go to step 2 | **2** |
| Still all boxes | something else is wrong — see "If step 1 fails" below | — |
| Nothing renders at all / crash | `QNX_FONT_DIR` pointed at a *file* or a bad dir; the font mgr returned empty | fix the path, retry |

If Chinese renders but **Latin got worse** (different, still legible) — expected.
Noto Sans SC now serves everything; that is the trade-off described in README §3.

### If step 1 fails

1. `QNX_FONT_DIR` must be a **directory containing font files**, not the font
   file itself. `SkFontMgr_New_Custom_Directory` on a file yields zero families
   and Chromium renders nothing at all.
2. Confirm the directory is readable by the app's uid: `/accounts/1000/shared`
   is, but a folder you made under `/tmp` on the device may not be.
3. Confirm the font actually has the glyph:
   ```sh
   # 15811 == 0x4E2D == 中 ; expect a non-zero glyph id
   python3.2 -c "print(open('/accounts/1000/shared/misc/NotoSansSC-Regular.otf','rb').read()[100:400].hex())"
   ```
   (`verify_bar.py` already proved cmap coverage on the host, so this is only
   worth doing if you copied the wrong file.)

---

## Step 2 — install the patched `.bar`

Sideload `out/BerryBrowserCJK-3.0.3-build85.bar` with Sachesi, DDPB, or the
on-device installer. It installs **as "Berry Browser CJK", alongside** the
official "Berry Browser" — that is intentional, so you can compare and roll back.

```sh
# on-device alternative to Sachesi
cd /accounts/1000/shared/.installer
python3.2 installer.py /accounts/1000/shared/misc/BerryBrowserCJK-3.0.3-build85.bar
```

Launch **Berry Browser CJK** from the home screen, open the same Chinese page,
and compare against the official app side by side.

### Confirm from the log that the font dir resolved

```sh
grep 'app dir' /accounts/1000/shared/misc/berry-kbd.log | tail -1
```

It prints e.g. `BerryShell: app dir = /accounts/1000/appdata/<id>/app/native`.
`QNX_FONT_DIR` is that path plus `/fonts`. If Chinese is *still* boxes, the
directory almost certainly was not created by the installer — go to step 3.

---

## Step 3 — contingency: create `fonts/` by hand

Only needed if step 2 shows boxes. Run on the phone as the app's user:

```sh
sh on-device-fix.sh testQWe_Ss5gbzxAiMRN9hW3S50
```

(the first argument is the `Package-Id` from `META-INF/MANIFEST.MF` in the `.bar`
you installed; `unzip -p out/BerryBrowserCJK-3.0.3-build85.bar META-INF/MANIFEST.MF | grep '^Package-Id'`).
The script finds the app's asset dir, creates `fonts/`, and copies the font in.
Relaunch from the home screen.

---

## Step 4 — sanity sweep

| Page | What it proves |
|---|---|
| `https://zh.wikipedia.org/wiki/黑莓` | dense CJK body text |
| `https://www.baidu.com` | CJK + CJK punctuation `，。、！？（）《》` |
| `https://www.taobao.com` | CJK + Latin + digits mixed in one line |
| `https://github.com` | Latin unchanged, monospace blocks, emoji in prose |
| any page with `<pre>`/code | confirms the proportional-monospace side effect |

---

## Step 5 — Alt key and Chinese input (read this before testing either)

**Do not test Alt on a build 84 `.bar`.** On build 84 the Alt key never reaches
the app at all — that is [upstream issue #2](https://github.com/sw7ft/chromium-for-bb10/issues/2),
fixed in build 104/106. Anything you conclude from Alt on build 84 is worthless.
Install a build 106 `.bar` first.

Then separate the two questions, because they have different answers:

**5a. Does Alt work as a modifier?** Tap into the page, press **Alt+←** (or
Alt+→). You should navigate back/forward. If that works, Alt reaches the app and
the Alt fix is present.

**5b. Does Alt+Enter switch to a Chinese IME?** It will not, and that is
expected — see README §7. This is not a font problem and not something a `.bar`
repack can address:

* BB10's Pinyin IME and its candidate window come from the platform IME
  service. Cascades apps get it through the Qt QNX platform plugin's input
  context. Berry Browser is a Cascades-less `systemChrome=none` native
  `Qnx/Elf` app driving libscreen directly, so it has no IME context.
* The port adds none either — `KeyboardHook::CreateModifierKeyboardHook()`
  returns `nullptr`, and the `ui::InitializeInputMethod()` in
  `patches/qnx-port.patch` is only a trace marker.
* Upstream's "Alt key fixed" note is about Alt as a **modifier**, not the OS
  input-method toggle.
* The usual workaround — compose Chinese in a Cascades app and paste — is also
  closed, because the port stubs the clipboard with `ClipboardNonBacked`, an
  in-process clipboard with no system backend.

**Control experiment worth doing once:** do the same Alt+Enter test in the
**stock BlackBerry Browser** on the same device. If it works there and not in
Berry Browser, that confirms it is the app type (native vs Cascades), not your
device settings.

Bottom line: Berry Browser can **read** Chinese, not **type** it. On a build 106
`.bar` from this repo that is the expected end state.

---

## Rolling back

Delete **Berry Browser CJK** from Settings → Apps. The official **Berry Browser**
was never touched: different `Package-Id`, different `appdata` directory, and
`content_shell.exe` is byte-identical to the release (checked by `verify_bar.py`).
