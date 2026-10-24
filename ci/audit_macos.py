"""Audit the final Apple Silicon extension and its deployment target."""
from __future__ import annotations

import re
import subprocess

from ci.audit import PRIVATE


def inspect_text(exports, imports, libraries, load_commands, architecture):
    defined = [line.split()[-1] for line in exports.splitlines() if line.strip()]
    needed = [line.strip().split(" (")[0] for line in libraries.splitlines()[1:] if line.strip()]
    minimums = re.findall(r"\bminos\s+(\d+\.\d+(?:\.\d+)?)", load_commands)
    minimums += re.findall(r"cmd LC_VERSION_MIN_MACOSX\s+cmdsize \d+\s+version (\d+\.\d+(?:\.\d+)?)", load_commands)
    errors = []
    if defined != ["_PyInit__mysql"]:
        errors.append(f"Unexpected exports: {defined}")
    if architecture.strip() != "arm64":
        errors.append(f"Unexpected architecture: {architecture.strip()}")
    for name in needed:
        if not name.startswith(("/usr/lib/", "/System/Library/")):
            errors.append(f"Non-system dynamic dependency: {name}")
    for line in imports.splitlines():
        if line.strip() and PRIVATE.match(line.split()[-1].lstrip("_")):
            errors.append(f"Unresolved private dependency: {line.strip()}")
    if not minimums:
        errors.append("Missing macOS deployment target")
    elif any(tuple(map(int, v.split(".")[:2])) > (11, 0) for v in minimums):
        errors.append(f"Deployment target exceeds macOS 11.0: {minimums}")
    return dict(exports=defined, needed=needed, minimum_macos=minimums,
                architecture=architecture.strip(), errors=errors)


def audit(path):
    def out(*args):
        return subprocess.check_output(args, text=True)
    return inspect_text(out("nm", "-gU", str(path)), out("nm", "-u", str(path)),
                        out("otool", "-L", str(path)), out("otool", "-l", str(path)),
                        out("lipo", "-archs", str(path)))
