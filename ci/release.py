"""Create one GitHub Release per distribution version from tested artifacts."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from ci.common import ROOT, abi, config, run


def release_plan(bundle, c=None):
    c = c or config()
    bundle = Path(bundle)
    releases = []
    for branch, upstream in c["upstream"].items():
        version = f"{upstream['version']}.post{c['build_revision']}"
        wheels = sorted((bundle / "wheelhouse").glob(f"*-{version}-*.whl"))
        if len(wheels) != len(upstream["python"]) * 2:
            raise RuntimeError(f"Incomplete wheel set for {version}: {len(wheels)}")
        releases.append(dict(version=version, tag=f"v{version}", wheels=wheels,
                             latest=branch == "current"))
    return releases


def release_notes(release, repository, c=None):
    c = c or config()
    version, tag = release["version"], release["tag"]
    python_versions = {abi(py): py for py in c["python"]}
    lines = [f"# mysqlclient-static {version}", "",
             f"[English guide](https://github.com/{repository}/blob/{tag}/README.md) | "
             f"[简体中文](https://github.com/{repository}/blob/{tag}/README_CN.md)", "",
             "Built and tested on Linux AMD64 and macOS ARM64.", "",
             "| Python | Platform | Download |", "|---|---|---|"]
    for wheel in release["wheels"]:
        _, _, wheel_abi, platform = wheel.stem.rsplit("-", 3)
        label = "macOS ARM64" if platform.startswith("macosx") else "Linux AMD64"
        lines.append(f"| {python_versions[wheel_abi]} | {label} | "
                     f"[Wheel](https://github.com/{repository}/releases/download/{tag}/{wheel.name}) |")
    example = release["wheels"][0].name
    lines += ["", "Download the wheel matching your Python version and platform, then install offline:",
              "", "```bash", "python -m pip install --no-index \\", f"  ./{example}", "```", "",
              "The same wheels are published on PyPI:", "", "```bash",
              f"python -m pip install mysqlclient-static=={version}", "```", "",
              "Both READMEs, complete source bundles and native build inventories are attached.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    notes = ROOT / ".work/release-notes"
    notes.mkdir(parents=True, exist_ok=True)
    common = [ROOT / "README.md", ROOT / "README_CN.md"]
    common += sorted((args.bundle / "release").glob("corresponding-source-*.tar.gz"))
    common += sorted((args.bundle / "release").glob("wheels-*.json"))
    for release in release_plan(args.bundle):
        body = notes / f"{release['version']}.md"
        body.write_text(release_notes(release, os.environ["GH_REPO"]))
        print(run(["gh", "release", "create", release["tag"], *release["wheels"], *common,
                   "--target", args.target, "--title", f"mysqlclient-static {release['version']}",
                   "--notes-file", body, "--latest" if release["latest"] else "--latest=false"]))


if __name__ == "__main__":
    main()
