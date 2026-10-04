#!/usr/bin/env python3
"""Repackage the official Berry Browser .bar with a working CJK font directory.

No Chromium rebuild. The prebuilt content_shell.exe already honours
QNX_FONT_DIR at run time; we just

  1. ship a font that contains BOTH Latin and Simplified Chinese,
  2. point QNX_FONT_DIR at it, computed at launch from /proc/self/exefile by a
     two-string patch of native/launcher (see patch_launcher.py),
  3. regenerate META-INF/MANIFEST.MF (SHA-512 digests + fresh package ids so it
     installs ALONGSIDE the official build and can be removed again),
  4. keep bar-descriptor-v3.xml consistent.

Usage
-----
    python3 build_bar.py --font fonts/NotoSansSC-Regular.otf
    python3 build_bar.py --font fonts/NotoSansCJKsc-Regular.otf \\
                         --name "Berry Browser CJK" --build 85

Everything is written to ./out/.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import os
import re
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch_launcher  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# The official release we repackage. Override with --src. 61 MB, so it is not
# committed -- it is downloaded on demand.
RELEASE_URL = (
    "https://github.com/sw7ft/chromium-for-bb10/raw/main/releases/"
    "BerryBrowserV3-3.0.2-build84.bar"
)
DEFAULT_SRC = os.path.join(HERE, "work", "BerryBrowserV3-3.0.2-build84.bar")


def ensure_source(path: str) -> str:
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    print(f"source .bar not present, downloading {RELEASE_URL}")
    try:
        import urllib.request

        with urllib.request.urlopen(RELEASE_URL) as r, open(path, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while chunk := r.read(1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done * 100 // total}% ({done >> 20} MiB)", end="")
            print()
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            f"could not download the source .bar ({e}).\n"
            f"Fetch it manually:\n  curl -L -o {path} {RELEASE_URL}"
        )
    if os.path.getsize(path) < 10_000_000:
        raise SystemExit(f"downloaded file looks wrong ({os.path.getsize(path)} bytes)")
    return path

FONT_SUBDIR = "fonts"

# Keep the entry order of the original MANIFEST.MF; this is what the Momentics
# "BlackBerry Elf BAR Packager" emits and the installer is happiest with.
NEW_ASSET = f"native/{FONT_SUBDIR}"

# Asset names whose Archive-Asset-Type must be preserved from the source
# manifest. Everything else is plain data; the type is derived from the original.


def urlsafe_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def b64_field(value: str, width: int = 17) -> str:
    """Reproduce the dev-mode id scheme used by the official BAR.

    Package-Version-Id / Package-Author-Id are  base64(value space-padded to
    `width` bytes) truncated to 23 chars.  Package-Id is the same shape over a
    17-byte digest of the package name.
    """
    raw = (value + " " * width)[:width].encode()
    return base64.b64encode(raw).decode()[:23]


def b64_digest_field(seed: str, width: int = 17) -> str:
    raw = hashlib.sha1(seed.encode()).digest()[:width]
    return urlsafe_b64(raw)[:23]


def parse_manifest(text: str):
    """Return (header_lines, [(asset_name, type_or_None), ...]) preserving order."""
    header, assets = [], []
    current_name, current_type = None, None
    for line in text.splitlines():
        if line.startswith("Archive-Asset-Name: "):
            if current_name is not None:
                assets.append((current_name, current_type))
            current_name = line.split(": ", 1)[1].strip()
            current_type = None
        elif line.startswith("Archive-Asset-Type: "):
            current_type = line.split(": ", 1)[1].strip()
        elif line.startswith("Archive-Asset-SHA-512-Digest: "):
            pass
        elif current_name is None:
            header.append(line)
    if current_name is not None:
        assets.append((current_name, current_type))
    return header, assets


def build_manifest(header, assets, digests, ids, app_name, entry_point):
    out = []
    for line in header:
        if line.startswith("Package-Name:"):
            out.append(f"Package-Name: {ids['package_name']}")
        elif line.startswith("Package-Id:"):
            out.append(f"Package-Id: {ids['package_id']}")
        elif line.startswith("Package-Version:"):
            out.append(f"Package-Version: {ids['package_version']}")
        elif line.startswith("Package-Version-Id:"):
            out.append(f"Package-Version-Id: {ids['version_id']}")
        elif line.startswith("Package-Author-Id:"):
            out.append(f"Package-Author-Id: {ids['author_id']}")
        elif line.startswith("Application-Id:"):
            out.append(f"Application-Id: {ids['package_id']}")
        elif line.startswith("Application-Name:"):
            out.append(f"Application-Name: {app_name}")
        elif line.startswith("Application-Version:"):
            out.append(f"Application-Version: {ids['package_version']}")
        elif line.startswith("Application-Version-Id:"):
            out.append(f"Application-Version-Id: {ids['version_id']}")
        elif line.startswith("Entry-Point-Name:"):
            out.append(f"Entry-Point-Name: {app_name}")
        elif line.startswith("Invoke-Target-Label:"):
            out.append(f"Invoke-Target-Label: {app_name}")
        elif line.startswith("Entry-Point:"):
            out.append(f"Entry-Point: {entry_point}")
        else:
            out.append(line)

    for name, atype in assets:
        digest = digests[name]
        out.append("")
        out.append(f"Archive-Asset-Name: {name}")
        out.append(f"Archive-Asset-SHA-512-Digest: {digest}")
        if atype:
            out.append(f"Archive-Asset-Type: {atype}")
    return "\n".join(out) + "\n"


def patch_descriptor(xml: str, package_name: str, version: str, build: str,
                     font_entry: str) -> str:
    xml = re.sub(r"<id>[^<]*</id>", f"<id>{package_name}</id>", xml, count=1)
    xml = re.sub(r"<versionNumber>[^<]*</versionNumber>",
                 f"<versionNumber>{version}</versionNumber>", xml, count=1)
    xml = re.sub(r"<buildId>[^<]*</buildId>", f"<buildId>{build}</buildId>",
                 xml, count=1)
    xml = re.sub(r'<invoke-target id="[^"]*"',
                 f'<invoke-target id="{package_name}"', xml)
    if font_entry not in xml:
        marker = '    <!-- Local start page'
        add = (f"    <!-- CJK: Latin + Simplified Chinese in one font, loaded via\n"
               f"         QNX_FONT_DIR (set by the launcher from /proc/self/exefile).\n"
               f"         The QNX port has no per-character fallback, so this font\n"
               f"         must be the ONLY font in the directory -- it then serves\n"
               f"         Latin and CJK alike. -->\n"
               f'    <asset path="{font_entry}">{font_entry}</asset>\n\n')
        if marker in xml:
            xml = xml.replace(marker, add + marker, 1)
        else:
            xml = xml.replace("</qnx>", add + "</qnx>")
    return xml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=DEFAULT_SRC,
                    help="source .bar (downloaded if absent)")
    ap.add_argument("--font", required=True, help="TTF/OTF with Latin + CJK")
    ap.add_argument("--name", default="Berry Browser CJK",
                    help="on-device application name")
    ap.add_argument("--package", default="com.sw7ft.BerryShellV3CJK",
                    help="new Package-Name (must differ from the original so "
                         "the two apps can coexist)")
    ap.add_argument("--version", default="3.0.3")
    ap.add_argument("--build", default="85")
    ap.add_argument("--outdir", default=os.path.join(HERE, "out"))
    ap.add_argument("--font-name", default=None,
                    help="file name inside the BAR (default: source file name)")
    args = ap.parse_args()

    ensure_source(args.src)
    if not os.path.exists(args.font):
        raise SystemExit(f"font not found: {args.font}")

    font_name = args.font_name or os.path.basename(args.font)
    font_asset = f"{NEW_ASSET}/{font_name}"
    package_version = f"{args.version}.{args.build}"

    os.makedirs(args.outdir, exist_ok=True)
    out_bar = os.path.join(
        args.outdir,
        f"BerryBrowserCJK-{args.version}-build{args.build}.bar",
    )

    with zipfile.ZipFile(args.src) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}
        infos = {i.filename: i for i in z.infolist()}

    manifest_name = "META-INF/MANIFEST.MF"
    header, assets = parse_manifest(blobs[manifest_name].decode())
    asset_types = dict(assets)
    order = [n for n, _ in assets]

    # --- 1. payload ------------------------------------------------------
    print("payload")
    blobs["native/launcher"] = patch_launcher.patch(blobs["native/launcher"])
    with open(args.font, "rb") as f:
        font_bytes = f.read()
    blobs[font_asset] = font_bytes
    print(f"  added  {font_asset} ({len(font_bytes)} bytes, "
          f"sha256 {hashlib.sha256(font_bytes).hexdigest()[:16]}…)")

    # --- 2. ids ----------------------------------------------------------
    print("manifest ids")
    ids = {
        "package_name": args.package,
        "package_id": "test" + b64_digest_field(args.package),
        "package_version": package_version,
        "version_id": "test" + b64_field(package_version),
        "author_id": "test" + b64_field("sw7ft"),
    }
    for k, v in ids.items():
        print(f"  {k:17s} {v}")

    # --- 3. descriptor ---------------------------------------------------
    descriptor_name = next(n for n in names if n.startswith("native/bar-descriptor"))
    blobs[descriptor_name] = patch_descriptor(
        blobs[descriptor_name].decode(),
        args.package, args.version, args.build,
        f"{FONT_SUBDIR}/{font_name}",
    ).encode()
    print(f"descriptor")
    print(f"  patched {descriptor_name}")

    # --- 4. manifest digests --------------------------------------------
    print("manifest")
    if font_asset not in order:
        order.append(font_asset)
        asset_types[font_asset] = None
    digests = {
        n: base64.b64encode(hashlib.sha512(blobs[n]).digest()).decode()
        for n in order
    }
    entry_point = next(
        line.split(": ", 1)[1]
        for line in blobs[manifest_name].decode().splitlines()
        if line.startswith("Entry-Point:")
    )
    print(f"  entry-point: {entry_point}")
    blobs[manifest_name] = build_manifest(
        header, [(n, asset_types[n]) for n in order], digests, ids,
        args.name, entry_point,
    ).encode()
    print(f"  rewrote {manifest_name} ({len(blobs[manifest_name])} bytes, "
          f"{len(order)} assets)")

    # --- 5. write --------------------------------------------------------
    print("write")
    tmp = out_bar + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        # MANIFEST first, as the packager does.
        for name in [manifest_name] + [n for n in order]:
            z.writestr(name, blobs[name])
        # Explicit directory entry so the installer has something to mkdir.
        z.writestr(zipfile.ZipInfo(f"{NEW_ASSET}/"), b"")
    shutil.move(tmp, out_bar)

    size = os.path.getsize(out_bar)
    with open(out_bar + ".sha256", "w") as f:
        f.write(f"{hashlib.sha256(open(out_bar,'rb').read()).hexdigest()}  "
                f"{os.path.basename(out_bar)}\n")
    print(f"  {out_bar}  {size} bytes ({size/1e6:.1f} MB)")
    print()
    print("verify before sideloading:")
    print(f"  unzip -l {out_bar} | grep -E 'fonts|launcher'")
    print(f"  unzip -p {out_bar} META-INF/MANIFEST.MF | head -20")
    return 0


if __name__ == "__main__":
    sys.exit(main())
