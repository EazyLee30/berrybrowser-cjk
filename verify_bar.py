#!/usr/bin/env python3
"""Verify a repackaged Berry Browser .bar before you sideload it onto a phone.

Checks, in order:
  1. every Archive-Asset-Name in META-INF/MANIFEST.MF exists in the zip
  2. every Archive-Asset-SHA-512-Digest matches the actual bytes
  3. native/launcher really exports QNX_FONT_DIR built from the asset dir
     (and no longer exports QNX_CA_BUNDLE)
  4. native/content_shell.exe is byte-identical to the source .bar (i.e. we did
     not accidentally touch the 96 MB engine binary)
  5. the shipped font really contains Latin AND Simplified Chinese, plus the
     CJK punctuation that Chinese web pages actually use
  6. package ids are the dev-mode 'test' shape and differ from the official app

Usage:  python3 verify_bar.py out/BerryBrowserCJK-3.0.3-build85.bar [--src OLD.bar]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import re
import struct
import sys
import zipfile

OK, BAD = "  ok  ", " FAIL "
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{OK if ok else BAD}] {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        failures.append(name)
    return ok


# --------------------------------------------------------------------------
# minimal cmap reader (format 4 and 12)
# --------------------------------------------------------------------------
def font_tables(d: bytes) -> set[str]:
    """Tag set of an sfnt/TTF/OTF (also works for a TTC's first face)."""
    off = struct.unpack(">I", d[12:16])[0] if d[:4] == b"ttcf" else 0
    n = struct.unpack(">H", d[off + 4 : off + 6])[0]
    return {d[off + 12 + 16 * i : off + 16 + 16 * i].decode("latin1") for i in range(n)}


def cmap_codepoints(path_or_bytes) -> set[int]:
    d = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    off = struct.unpack(">I", d[12:16])[0] if d[:4] == b"ttcf" else 0
    n = struct.unpack(">H", d[off + 4 : off + 6])[0]
    tables = {}
    for i in range(n):
        p = off + 12 + 16 * i
        tag = d[p : p + 4].decode("latin1")
        o, l = struct.unpack(">II", d[p + 8 : p + 16])
        tables[tag] = (o, l)
    if "cmap" not in tables:
        return set()
    co = tables["cmap"][0]
    ntab = struct.unpack(">H", d[co + 2 : co + 4])[0]
    best = None
    for i in range(ntab):
        pid, eid, so = struct.unpack(">HHI", d[co + 4 + 8 * i : co + 12 + 8 * i])
        fmt = struct.unpack(">H", d[co + so : co + so + 2])[0]
        if fmt in (4, 12) and (best is None or fmt == 12):
            best = (fmt, co + so)
    if not best:
        return set()
    fmt, so = best
    chars: set[int] = set()
    if fmt == 4:
        segx2 = struct.unpack(">H", d[so + 6 : so + 8])[0]
        seg = segx2 // 2
        ends = struct.unpack(f">{seg}H", d[so + 14 : so + 14 + segx2])
        sp = so + 16 + segx2
        starts = struct.unpack(f">{seg}H", d[sp : sp + segx2])
        dp = sp + segx2
        deltas = struct.unpack(f">{seg}h", d[dp : dp + segx2])
        rp = dp + segx2
        ranges = struct.unpack(f">{seg}H", d[rp : rp + segx2])
        for i in range(seg):
            if starts[i] == 0xFFFF:
                continue
            for c in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if ranges[i] == 0:
                    g = (c + deltas[i]) & 0xFFFF
                else:
                    gi = rp + i * 2 + ranges[i] + (c - starts[i]) * 2
                    if gi + 2 > len(d):
                        continue
                    g = struct.unpack(">H", d[gi : gi + 2])[0]
                    if g:
                        g = (g + deltas[i]) & 0xFFFF
                if g:
                    chars.add(c)
    else:
        ngroups = struct.unpack(">I", d[so + 12 : so + 16])[0]
        for i in range(ngroups):
            s, e, _g = struct.unpack(">III", d[so + 16 + 12 * i : so + 28 + 12 * i])
            if e - s < 70000:
                chars.update(range(s, e + 1))
    return chars


# Sample of what Chinese-language web pages actually need. If any of these is
# missing you get a visible tofu box on a very common page.
SAMPLE = [
    ("ASCII", 0x41), ("latin é", 0xE9), ("euro €", 0x20AC), ("em dash —", 0x2014),
    ("ellipsis …", 0x2026), ("中", 0x4E2D), ("文", 0x6587), ("你", 0x4F60),
    ("好", 0x597D), ("国", 0x56FD), ("人", 0x4EBA), ("民", 0x6C11),
    ("，", 0xFF0C), ("。", 0x3002), ("、", 0x3001), ("《", 0x300A),
    ("！", 0xFF01), ("？", 0xFF1F), ("：", 0xFF1A), ("“", 0x201C),
    ("￥", 0xFFE5), ("〇", 0x3007), ("〇二", 0x4E8C),
]
EXT_A = [0x3400, 0x4DB5]  # CJK Ext A start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bar")
    ap.add_argument("--src", default=None,
                    help="original .bar, to prove content_shell.exe is untouched")
    args = ap.parse_args()

    z = zipfile.ZipFile(args.bar)
    names = z.namelist()
    manifest = z.read("META-INF/MANIFEST.MF").decode()

    print(f"verifying {args.bar}")
    print(f"  {len(names)} zip entries\n")

    # 1 + 2 ---------------------------------------------------------------
    assets = re.findall(r"^Archive-Asset-Name: (.+)$", manifest, re.M)
    digests = dict(
        zip(
            re.findall(r"^Archive-Asset-Name: (.+)$", manifest, re.M),
            re.findall(r"^Archive-Asset-SHA-512-Digest: (.+)$", manifest, re.M),
        )
    )
    check("manifest lists at least the original 17 assets", len(assets) >= 17,
          f"{len(assets)} assets")
    missing = [a for a in assets if a not in names]
    check("every manifest asset exists in the zip", not missing, str(missing))
    bad = []
    for a in assets:
        if a in names:
            want = digests[a]
            got = base64.b64encode(hashlib.sha512(z.read(a)).digest()).decode()
            if want != got:
                bad.append(a)
    check("every SHA-512 digest matches", not bad, str(bad))
    unlisted = [n for n in names
                if n not in assets and not n.endswith("/") and n != "META-INF/MANIFEST.MF"]
    check("no unlisted payload files", not unlisted, str(unlisted))
    check("fonts directory entry present (helps the installer mkdir)",
          any(n.endswith("/") for n in names),
          [n for n in names if n.endswith("/")])

    # 3 --------------------------------------------------------------------
    launcher = z.read("native/launcher")
    check("launcher exports QNX_FONT_DIR", b"QNX_FONT_DIR\x00" in launcher)
    check("launcher builds it from the asset dir",
          b"%s/fonts\x00" in launcher,
          "format string '%s/fonts' present")
    check("launcher no longer exports QNX_CA_BUNDLE",
          b"QNX_CA_BUNDLE" not in launcher)
    check("launcher still execs content_shell.exe",
          b"%s/content_shell.exe\x00" in launcher)

    # 4 --------------------------------------------------------------------
    if args.src:
        orig = zipfile.ZipFile(args.src)
        for f in ("native/content_shell.exe", "native/icudtl.dat",
                  "native/home.html", "native/icon.png"):
            if f in orig.namelist() and f in names:
                check(f"{f} byte-identical to source",
                      hashlib.sha256(orig.read(f)).hexdigest()
                      == hashlib.sha256(z.read(f)).hexdigest())

    # 5 --------------------------------------------------------------------
    fonts = [n for n in names if n.lower().endswith((".otf", ".ttf", ".ttc", ".otc"))]
    check("exactly one font shipped", len(fonts) == 1, str(fonts))
    if len(fonts) == 1:
        chars = cmap_codepoints(z.read(fonts[0]))
        missing_glyphs = [nm for nm, cp in SAMPLE if cp not in chars]
        check("font covers the Latin + CJK sample", not missing_glyphs,
              "missing: " + ", ".join(missing_glyphs) if missing_glyphs else
              f"{len(chars)} codepoints")
        check("font covers CJK Unified Ideographs",
              sum(1 for c in chars if 0x4E00 <= c <= 0x9FFF) > 20000,
              f"{sum(1 for c in chars if 0x4E00 <= c <= 0x9FFF)} CJK glyphs")
        check("font covers CJK Ext A", sum(1 for c in chars if EXT_A[0] <= c <= EXT_A[1]) > 1000,
              f"{sum(1 for c in chars if EXT_A[0] <= c <= EXT_A[1])} Ext-A glyphs")
        tables = font_tables(z.read(fonts[0]))
        check("font is not a variable font (old Skia/FreeType on QNX)",
              "fvar" not in tables, "tables: " + " ".join(sorted(tables)))

    # 6 --------------------------------------------------------------------
    def field(k: str) -> str:
        m = re.search(rf"^{k}: (.+)$", manifest, re.M)
        return m.group(1).strip() if m else ""

    # "test" + 23 base64 chars = 27, exactly as the official build emits.
    check("Package-Id is dev-mode shaped",
          field("Package-Id").startswith("test") and len(field("Package-Id")) == 27,
          field("Package-Id"))
    check("Application-Id == Package-Id",
          field("Application-Id") == field("Package-Id"))
    check("Package-Version-Id is dev-mode shaped",
          field("Package-Version-Id").startswith("test")
          and len(field("Package-Version-Id")) == 27,
          field("Package-Version-Id"))
    check("Application-Version-Id == Package-Version-Id",
          field("Application-Version-Id") == field("Package-Version-Id"))
    ep = field("Entry-Point")
    check("Entry-Point still points at the launcher",
          "app/native/launcher" in ep, ep)
    check("package differs from the official build",
          field("Package-Name") != "com.sw7ft.BerryShellV3",
          f"{field('Package-Name')} / {field('Application-Name')}")

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("all checks passed — safe to sideload")
    return 0


if __name__ == "__main__":
    sys.exit(main())
