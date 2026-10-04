#!/usr/bin/env python3
"""Extra launcher patches for site compatibility.

All of these are still in-place .rodata string edits in native/launcher, no code
is injected and no section moves. Two techniques are used:

FORCING A MARKER ON
    launcher.c has

        static int marker_exists(const char* name) {
          char path[512];
          snprintf(path, sizeof(path), "%s%s", kSharedMisc, name);
          return access(path, F_OK) == 0;
        }

    so replacing the marker name literal with the empty string makes it
    snprintf("/accounts/1000/shared/misc/" + "") -- a directory that always
    exists -- and marker_exists() returns true unconditionally. The feature it
    guards is then always on, with no marker file and no rebuild.

REMOVING A FLAG
    A command-line switch Chromium does not recognise is parsed, stored, and
    never queried. Renaming e.g. "--use-fake-ui-for-media-stream" to an
    unrecognised name of the same or shorter length therefore removes the
    behaviour without touching the argv bookkeeping.

Every substitution must SHRINK or stay the same length, and every needle must be
unique, or this refuses to write.
"""

from __future__ import annotations

# (name, needle, replacement, why)
FORCE_ON = [
    ("desktop-ua", b"berry-desktop.enable\x00", b"\x00",
     "present as desktop Chrome instead of mobile Chrome; the desktop web login "
     "path is by far the most exercised one"),
    ("no-serviceworker", b"berry-sw.disable\x00", b"\x00",
     "the launcher enables ServiceWorker by default, which is unusual for a "
     "browser and changes how several login flows behave"),
    ("no-blocklist", b"berry-block.disable\x00", b"\x00",
     "drop the --host-resolver-rules NOTFOUND blocklist so host resolution "
     "cannot be the reason a site misbehaves"),
    ("http1", b"berry-http1.enable\x00", b"\x00",
     "force --disable-http2; the launcher itself records an h2 ALPN quirk "
     "against Google (googlevideo), so HTTP/1.1 is the conservative choice"),
]

NEUTRALISE = [
    ("fake-media-ui", b"--use-fake-ui-for-media-stream\x00", b"--x-off-fake-ui-media\x00",
     "auto-grants getUserMedia; sign-up/login flows that probe the camera can "
     "walk into a dead end with a fake device attached"),
    ("fake-media-dev", b"--use-fake-device-for-media-stream\x00", b"--x-off-fake-dev-media\x00",
     "same, for the capture side"),
]


def apply(data: bytes, which: tuple[str, ...] = ()) -> tuple[bytes, list[str]]:
    buf = bytearray(data)
    log: list[str] = []
    edits = FORCE_ON + NEUTRALISE
    if which:
        edits = [e for e in edits if e[0] in which]

    for name, needle, repl, why in edits:
        n = data.count(needle)
        if n == 0:
            log.append(f"  skip    {name:16s} not present in this build")
            continue
        if n != 1:
            raise SystemExit(
                f"compat: {name}: needle {needle!r} occurs {n} times, "
                f"refusing to guess which copy is the switch/guard"
            )
        if len(repl) > len(needle):
            raise SystemExit(f"compat: {name}: replacement longer than needle")
        off = data.find(needle)
        buf[off : off + len(repl)] = repl
        log.append(f"  patched {name:16s} @ 0x{off:06x}  "
                   f"{needle[:-1].decode()} -> {repl[:-1].decode() or '(empty)'}")
        log.append(f"          because {why}")

    out = bytes(buf)
    for name, needle, repl, _ in edits:
        if needle in out:
            raise SystemExit(f"compat: post-patch check failed: {name} still present")
    if len(out) != len(data):
        raise SystemExit("compat: size changed")
    return out, log


PROFILES = {
    "plain": (),
    "compat": tuple(e[0] for e in FORCE_ON + NEUTRALISE),
}
