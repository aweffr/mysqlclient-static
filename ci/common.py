"""Shared utilities: Python 3.9+, standard library only."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def config():
    return json.loads((ROOT / "versions.json").read_text())

def matrix_config():
    c = config()
    if os.environ.get("MCS_PLATFORM") == "macos":
        c["mysql"] = [d for d in c["mysql"] if d["version"] in c["macos_mysql"]]
        c["runtime_mysql"] = [d["version"] for d in c["mysql"]]
        c["distros"] = []
    return c

def run(args, *, cwd=None, env=None, input=None, timeout=900, log=None):
    p = subprocess.run([str(a) for a in args], cwd=cwd, env=env, input=input,
                       text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       timeout=timeout)
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(p.stdout)
    if p.returncode:
        raise RuntimeError(f"Command failed ({p.returncode}): {args[0]}\n{p.stdout[-12000:]}")
    return p.stdout.strip()

def download(url, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mysqlclient-static-build/1"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
            target.write_bytes(data)
            return target
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def extract(archive, target):
    """Extract trusted-pinned archives, with path/link checks as defense in depth.

    Native git archives may contain legitimate relative symlinks. Python's data
    filter resolves each member at extraction time, including link chains.
    """
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as t:
        for m in t.getmembers():
            out = (target / m.name).resolve()
            if Path(m.name).is_absolute() or (target != out and target not in out.parents):
                raise ValueError(f"Unsafe archive path: {m.name}")
            if not (m.isfile() or m.isdir() or m.issym() or m.islnk()):
                raise ValueError(f"Unsupported archive entry: {m.name}")
            if m.issym() or m.islnk():
                base = out.parent if m.issym() else target
                linked = (base / m.linkname).resolve()
                if Path(m.linkname).is_absolute() or (linked != target and target not in linked.parents):
                    raise ValueError(f"Unsafe archive link: {m.name}")
                if not hasattr(tarfile, "data_filter"):
                    raise ValueError("Safe link extraction requires an updated Python tarfile module")
        try:
            t.extractall(target, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        except tarfile.FilterError as exc:
            raise ValueError(f"Unsafe archive member: {exc}") from exc

def version_tuple(s):
    return tuple(int(x) for x in s.split(".")[:3])

def abi(py):
    return "cp" + py.replace(".", "")

def python_tag(py):
    """Free-threaded wheels share the Python tag, but have a distinct ABI."""
    return abi(py.removesuffix("t"))

def python_request(py):
    """Require the selected ABI when regular and free-threaded Pythons coexist."""
    if py.endswith("t"):
        return py
    # UV can select free-threaded interpreters by default starting with 3.14.
    return f"{py}+gil" if version_tuple(py) >= (3, 14) else py

def create_python_environment(py, directory):
    request = python_request(py)
    if request.endswith("+gil"):
        # UV can discover +gil interpreters, but downloads use the plain version.
        run(["uv", "python", "install", "--no-bin", py], timeout=300)
    run(["uv", "venv", "--seed", "--python", request, directory], timeout=300)

def upstream_for(py):
    for item in config()["upstream"].values():
        if py in item["python"]:
            return item
    raise ValueError(f"No upstream for Python {py}")

def wheel_for(directory, py, platform="manylinux"):
    tag = abi(py)
    matches = list(Path(directory).glob(f"*-{python_tag(py)}-{tag}-{platform}*.whl"))
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {tag} wheel, found {matches}")
    return matches[0]

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)
