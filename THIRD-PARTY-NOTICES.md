# Third-party notices

The tooling in this repository (the Python scripts and shell scripts) is MIT
licensed — see [LICENSE](LICENSE). The things those tools *package* are not.

## Berry Browser

`build_bar.py` downloads sw7ft's published `.bar` from
[sw7ft/chromium-for-bb10](https://github.com/sw7ft/chromium-for-bb10) /
[sw7ft/berry-browser](https://github.com/sw7ft/berry-browser), patches two
strings in the already-compiled launcher, and repackages the archive.

**No Berry Browser source or binary is committed to this repository.** The
`content_shell.exe` inside the built `.bar` files is byte-for-byte identical to
the upstream release, which `verify_bar.py` asserts on every build. This project
is not affiliated with BlackBerry Limited and is not endorsed by sw7ft.

## Fonts

The `.bar` files bundle one font. Both candidates are licensed under the
**SIL Open Font License 1.1**, which permits redistribution inside a larger work
such as an application archive:

| Font | Licence | Upstream |
|---|---|---|
| `NotoSansSC-Regular.otf` | SIL OFL 1.1 | [notofonts/noto-cjk](https://github.com/notofonts/noto-cjk) |
| `NotoSansCJKsc-Regular.otf` | SIL OFL 1.1 | [notofonts/noto-cjk](https://github.com/notofonts/noto-cjk) |

Full details, sizes, glyph coverage and SHA-256 sums in
[fonts/LICENSES.md](fonts/LICENSES.md).

## Chromium

Chromium itself is BSD-licensed by The Chromium Authors. This repository
contains none of its code — see the note above.
