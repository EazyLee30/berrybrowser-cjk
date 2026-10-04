#!/usr/bin/env python3
"""Give the Berry Browser launcher (native/launcher, ARM/QNX ELF) a working
QNX_FONT_DIR, using two in-place .rodata string substitutions.

WHY THIS EXISTS
---------------
The QNX port reads the font directory from the environment:

    const char* font_dir = getenv("QNX_FONT_DIR");
    if (!font_dir || !font_dir[0])
      font_dir = "/usr/fonts/font_repository";
    sk_sp<SkFontMgr> mgr = SkFontMgr_New_Custom_Directory(font_dir);

but nothing in the .bar ever sets it, and the only sane value is an ABSOLUTE
path derived from /proc/self/exefile -- which no static <env>/Entry-Point value
can express, because the launcher chdir()s away from the asset dir before it
execs content_shell.

The launcher already contains exactly one "compute a path from the asset dir
and export it" block:

    char ca[2200];
    snprintf(ca, sizeof(ca), "%s/root_store.certs", dir);
    if (access(ca, R_OK) == 0)
      setenv("QNX_CA_BUNDLE", ca, 1);

so we retarget that block at the fonts directory instead. Both substitutions
only ever SHRINK the strings, so nothing moves and no section grows.

  1. "QNX_CA_BUNDLE"        -> "QNX_FONT_DIR"    (14 bytes -> 13, +NUL slack)
  2. "%s/root_store.certs"  -> "%s/fonts"        (20 bytes ->  9)

Result: QNX_FONT_DIR=<asset dir>/fonts, absolute, correct on every BB10 model
and OS version, independent of the process cwd.

WHAT WE GIVE UP
---------------
QNX_CA_BUNDLE is no longer exported. That is safe for this build: the only
occurrence of the string inside content_shell.exe is in a child-process
environment forwarding list (patches/mp-gpu-navigation.patch, kForwardEnv),
the binary never reads it as a certificate path, HTTPS already runs with
--ignore-certificate-errors, and the port's own README states there is no root
CA store on the device.
"""

import argparse
import hashlib
import sys

# (label, needle, replacement) -- replacements must be strictly shorter and
# keep their NUL terminator.
PATCHES = [
    ("env-name", b"QNX_CA_BUNDLE\x00", b"QNX_FONT_DIR\x00"),
    ("path-tmpl", b"%s/root_store.certs\x00", b"%s/fonts\x00"),
]

# Sanity: the launcher must not already have been patched.
FORBIDDEN = b"QNX_FONT_DIR"


def patch(data: bytes, expect_patched: bool = False) -> bytes:
    buf = bytearray(data)
    report = []

    for label, needle, repl in PATCHES:
        count = data.count(needle)
        if count != 1:
            raise SystemExit(
                f"patch_launcher: {label}: expected exactly 1 occurrence of "
                f"{needle!r}, found {count}. Wrong launcher build? Aborting "
                f"without writing."
            )
        off = data.find(needle)
        if len(repl) > len(needle):
            raise SystemExit(f"patch_launcher: {label}: replacement too long")
        buf[off : off + len(repl)] = repl
        report.append((label, off, needle, repl))

    # Guard against double-patching: if the *source* already exported
    # QNX_FONT_DIR there is nothing of ours to find and the needle counts above
    # would already have failed. Kept as an explicit, readable assertion.
    if not expect_patched and FORBIDDEN in data:
        raise SystemExit(
            "patch_launcher: launcher already sets QNX_FONT_DIR "
            "(already patched? pass expect_patched=True)"
        )

    out = bytes(buf)

    # Verify by reading the strings back the way the code will.
    checks = []
    i = out.find(b"QNX_FONT_DIR\x00")
    checks.append(("env-name reads back", out[i : i + 13] == b"QNX_FONT_DIR\x00"))
    j = out.find(b"%s/fonts\x00")
    checks.append(("path template reads back", out[j : j + 9] == b"%s/fonts\x00"))
    checks.append(("QNX_CA_BUNDLE gone", b"QNX_CA_BUNDLE" not in out))
    checks.append(("size unchanged", len(out) == len(data)))
    for name, ok in checks:
        if not ok:
            raise SystemExit(f"patch_launcher: post-patch check failed: {name}")

    for label, off, needle, repl in report:
        print(
            f"  patched {label:11s} @ 0x{off:06x}  "
            f"{needle[:-1].decode()} -> {repl[:-1].decode()}"
        )
    for name, ok in checks:
        print(f"  check    {name:24s} {'ok' if ok else 'FAIL'}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("launcher", help="path to native/launcher (patched in place)")
    ap.add_argument(
        "--dry-run", action="store_true", help="do not write, just verify offsets"
    )
    args = ap.parse_args()

    with open(args.launcher, "rb") as f:
        original = f.read()

    print(f"patch_launcher: {args.launcher} ({len(original)} bytes)")
    print(f"  sha256 before: {hashlib.sha256(original).hexdigest()}")
    patched = patch(original)
    print(f"  sha256 after : {hashlib.sha256(patched).hexdigest()}")

    if args.dry_run:
        print("  dry run: not writing")
        return 0
    with open(args.launcher, "wb") as f:
        f.write(patched)
    print("  written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
