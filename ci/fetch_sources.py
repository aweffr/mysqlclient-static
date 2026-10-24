"""Download fixed upstream sources and verify every source identity."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from ci.common import ROOT, config, download, extract, run, sha256, write_json

def main():
    c = config()
    source = ROOT / ".work/sources"
    archives = ROOT / ".work/source-archives"
    source.mkdir(parents=True, exist_ok=True)
    archives.mkdir(parents=True, exist_ok=True)
    provenance = []
    for name, dep in c["native"].items():
        dest = source / name
        if dest.exists():
            shutil.rmtree(dest)
        gitdir = ROOT / ".work/git" / name
        if gitdir.exists():
            shutil.rmtree(gitdir)
        gitdir.mkdir(parents=True)
        run(["git", "init", "-q", gitdir])
        run(["git", "-C", gitdir, "remote", "add", "origin",
             f"https://github.com/{dep['repository']}.git"])
        run(["git", "-C", gitdir, "fetch", "--depth=1", "origin", f"refs/tags/{dep['tag']}"], timeout=900)
        obj = run(["git", "-C", gitdir, "rev-parse", "FETCH_HEAD"])
        if obj != dep["git_object"]:
            raise RuntimeError(f"Source identity changed: {name}: {obj}")
        commit = run(["git", "-C", gitdir, "rev-parse", "FETCH_HEAD^{commit}"])
        archive = archives / f"{name}-{dep['version']}.tar.gz"
        run(["git", "-C", gitdir, "archive", "--format=tar.gz", f"--output={archive}", commit])
        extract(archive, dest)
        provenance.append(dict(component=name, version=dep["version"], commit=commit,
                               git_object=obj, sha256=sha256(archive)))
    for dep in c["upstream"].values():
        v = dep["version"]
        req = urllib.request.Request(f"https://pypi.org/pypi/mysqlclient/{v}/json")
        with urllib.request.urlopen(req, timeout=90) as r:
            metadata = json.load(r)
        item = next(x for x in metadata["urls"] if x["packagetype"] == "sdist")
        if item["digests"]["sha256"] != dep["sha256"]:
            raise RuntimeError(f"PyPI source checksum differs from lock: {v}")
        archive = download(item["url"], archives / f"mysqlclient-{v}.tar.gz")
        if sha256(archive) != dep["sha256"]:
            raise RuntimeError(f"Downloaded source checksum mismatch: {v}")
        dest = source / f"mysqlclient-{v}"
        if dest.exists():
            shutil.rmtree(dest)
        extract(archive, source)
        provenance.append(dict(component="mysqlclient", version=v, sha256=sha256(archive), url=item["url"]))
    write_json(ROOT / "reports/source-provenance.json", provenance)

if __name__ == "__main__":
    main()
