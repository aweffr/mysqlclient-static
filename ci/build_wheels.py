"""Build both upstream branches with cibuildwheel and audit the resulting wheels."""
from __future__ import annotations
import argparse
import json
import platform
import os
from pathlib import Path
import shutil
import sys
import tarfile
import zipfile
from ci.audit import audit as audit_linux
from ci.audit_macos import audit as audit_macos
from ci.symbols import symbol_index
from ci.common import ROOT, abi, config, run, sha256, upstream_for, write_json

PREFIX = Path("/opt/mysqlclient-static")

def stage_source(py, destination, *, source_root=None, prefix=PREFIX):
    c = config()
    upstream = upstream_for(py)
    src = (source_root or ROOT / ".work/sources") / f"mysqlclient-{upstream['version']}"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(src, destination)
    for name in ("build", "dist", "src/mysqlclient.egg-info"):
        path = destination / name
        if path.exists():
            shutil.rmtree(path)
    version = f"{upstream['version']}.post{c['build_revision']}"
    requires = ">=3.9,<3.10" if py == "3.9" else ">=3.10,<3.15"
    # Keep MySQLdb.release and the extension's upstream version_info unchanged.
    # Only the distribution name/version change; Django's runtime check remains honest.
    text = f"""[build-system]
requires = ["setuptools==80.9.0", "wheel==0.45.1"]
build-backend = "setuptools.build_meta"

[project]
name = "{c['distribution']}"
version = "{version}"
description = "Self-contained build of mysqlclient {upstream['version']}"
readme = "STATIC_BUILD.md"
requires-python = "{requires}"
license = "MIT"
license-files = ["LICENSES/*"]
classifiers = ["Programming Language :: Python :: 3", "Operating System :: POSIX :: Linux", "Operating System :: MacOS :: MacOS X"]

[project.urls]
Homepage = "https://github.com/aweffr/mysqlclient-static"
Source = "https://github.com/aweffr/mysqlclient-static"
Issues = "https://github.com/aweffr/mysqlclient-static/issues"
"Source archives" = "https://github.com/aweffr/mysqlclient-static/releases"

[tool.setuptools]
package-dir = {{"" = "src"}}
include-package-data = true

[tool.setuptools.packages.find]
where = ["src"]
include = ["MySQLdb*"]
namespaces = false

[tool.setuptools.package-data]
MySQLdb = ["_static_build.json", "README.md", "README_CN.md", "AGENTS.md", "api-symbols.json", "examples/*.py"]
"""
    (destination / "pyproject.toml").write_text(text)
    readme = (ROOT / "README.md").read_text().replace(
        "](README_CN.md)", f"](https://github.com/aweffr/mysqlclient-static/blob/v{version}/README_CN.md)")
    (destination / "STATIC_BUILD.md").write_text(readme)
    licenses = destination / "LICENSES"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", licenses / "mysqlclient-static-LICENSE")
    for pattern in ("LICENSE*", "COPYING*"):
        for notice in destination.glob(pattern):
            if notice.is_file():
                shutil.copy2(notice, licenses / f"mysqlclient-{notice.name}")
    for f in (ROOT / "licenses").glob("*"):
        if f.is_file():
            shutil.copy2(f, licenses / f.name)
    native_sources = ROOT / ".work/sources"
    for component, patterns in {"openssl":["LICENSE.txt", "NOTICE"], "connector":["COPYING.LIB"],
                                "zlib":["LICENSE"], "zstd":["LICENSE", "COPYING"]}.items():
        for filename in patterns:
            f = native_sources / component / filename
            if f.exists():
                shutil.copy2(f, licenses / f"{component}-{filename}")
    metadata = dict(distribution=c["distribution"], version=version, upstream=upstream["version"],
                    native=c["native"], platform="macosx_11_0_arm64" if sys.platform == "darwin" else c["platform"], python=py)
    write_json(destination / "src/MySQLdb/_static_build.json", metadata)
    package = destination / "src/MySQLdb"
    for name in ("README.md", "README_CN.md"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copy2(ROOT / "docs/agent-guide.md", package / "AGENTS.md")
    shutil.copytree(ROOT / "examples", package / "examples", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    write_json(package / "api-symbols.json", symbol_index(package))
    return version


def build_native(target):
    if target == "macos":
        prefix = ROOT / ".work/native"
        env = dict(os.environ, MCS_PREFIX=str(prefix))
        run(["bash", "ci/build_native.sh"], cwd=ROOT, env=env,
            timeout=3600, log=ROOT / "reports/native-build.log")
        write_json(ROOT / "reports/build-image.json", {
            "platform": platform.platform(), "xcode": run(["xcodebuild", "-version"])})
        return prefix
    image = "mysqlclient-static-builder:local"
    context = ROOT / ".work/build-image"
    context.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / ".work/sources", context / "sources", dirs_exist_ok=True)
    shutil.copy2(ROOT / "ci/build_native.sh", context)
    shutil.copy2(ROOT / "ci/exports.map", context)
    run(["docker", "build", "--platform=linux/amd64", "--build-arg",
         f"BASE={config()['build_image']}", "-f", ROOT / "ci/Dockerfile.build",
         "-t", image, context], timeout=3600, log=ROOT / "reports/native-build.log")
    write_json(ROOT / "reports/build-image.json", json.loads(run(["docker", "image", "inspect", image])))
    return PREFIX


def link_environment(target, prefix):
    archives = [prefix / "lib" / f"lib{n}.a" for n in
                ("mysqlclient-static", "ssl", "crypto", "zstd", "z")]
    cflags = f"-I{prefix}/include/mariadb -I{prefix}/include -O2 -fPIC -fvisibility=hidden"
    ldflags = " ".join(map(str, archives))
    if target == "linux":
        cflags += " -march=x86-64"
        ldflags += " -Wl,--exclude-libs,ALL -Wl,--version-script=/opt/mysqlclient-static/exports.map -ldl -lm -pthread"
    else:
        cflags += " -arch arm64"
        ldflags += " -Wl,-exported_symbol,_PyInit__mysql -liconv"
    return {"MYSQLCLIENT_CFLAGS": cflags, "MYSQLCLIENT_LDFLAGS": ldflags}


def source_bundle(target, records):
    bundle = ROOT / f"release/corresponding-source-{target}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        for f in (ROOT / ".work/source-archives").glob("*.tar.gz"):
            tar.add(f, arcname=f"upstream/{f.name}")
        for name in ("ci", "tests", ".github", "licenses", "versions.json", "README.md", "README_CN.md",
                     "LICENSE", "docs", "examples", "AGENTS.md", "pyproject.toml", "uv.lock", ".python-version"):
            tar.add(ROOT / name, arcname=f"build/{name}",
                    filter=lambda i: None if "__pycache__" in i.name else i)
        for name in ("source-provenance.json", "build-image.json"):
            tar.add(ROOT / "reports" / name, arcname=name)
    write_json(ROOT / f"release/wheels-{target}.json", records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=["linux", "macos"],
                        default="macos" if sys.platform == "darwin" else "linux")
    target = parser.parse_args().platform
    c = config()
    for name in ("reports", "wheelhouse", "release"):
        (ROOT / name).mkdir(exist_ok=True)
    prefix = build_native(target)
    env = os.environ.copy()
    env["CIBW_BUILD_FRONTEND"] = "build[uv]"
    env[f"CIBW_ARCHS_{target.upper()}"] = "arm64" if target == "macos" else "x86_64"
    flags = link_environment(target, prefix)
    env[f"CIBW_ENVIRONMENT_{target.upper()}"] = " ".join(
        f'{key}="{value}"' for key, value in flags.items())
    if target == "linux":
        env["CIBW_MANYLINUX_X86_64_IMAGE"] = "mysqlclient-static-builder:local"
    else:
        env["CIBW_ENVIRONMENT_MACOS"] += ' MACOSX_DEPLOYMENT_TARGET="11.0"'
    for branch in c["upstream"].values():
        src = ROOT / ".work/packages" / branch["version"]
        stage_source(branch["python"][0], src)
        suffix = "macosx_arm64" if target == "macos" else "manylinux_x86_64"
        env["CIBW_BUILD"] = " ".join(f"{abi(py)}-{suffix}" for py in branch["python"])
        run([sys.executable, "-m", "cibuildwheel", src, "--platform", target,
             "--config-file", ROOT / "pyproject.toml", "--output-dir", ROOT / "wheelhouse"],
            env=env, timeout=5400, log=ROOT / f"reports/build-{branch['version']}.log")
    records = []
    for wheel in sorted((ROOT / "wheelhouse").glob("*.whl")):
        unpack = ROOT / ".work/audit" / wheel.stem
        with zipfile.ZipFile(wheel) as archive:
            archive.extractall(unpack)
            for name in ("MySQLdb/README.md", "MySQLdb/README_CN.md", "MySQLdb/AGENTS.md",
                         "MySQLdb/examples/basic.py", "MySQLdb/examples/transactions.py",
                         "MySQLdb/examples/django_settings.py", "MySQLdb/examples/celery_task.py"):
                archive.read(name).decode("utf-8")
            symbols = json.loads(archive.read("MySQLdb/api-symbols.json"))
            if symbols["import_package"] != "MySQLdb" or not symbols["native_methods"]["MySQLdb._mysql.connection"]:
                raise RuntimeError("Missing upstream API symbol index")
        result = (audit_macos if target == "macos" else audit_linux)(next(unpack.glob("MySQLdb/_mysql*.so")))
        if result["errors"]:
            raise RuntimeError(f"Binary audit failed: {wheel.name}: {result['errors']}")
        records.append(dict(file=wheel.name, size=wheel.stat().st_size, audit=result))
    if len(records) != len(c["python"]):
        raise RuntimeError(f"Expected {len(c['python'])} wheels, got {len(records)}")
    write_json(ROOT / "reports/wheels.json", records)
    run(["clang" if target == "macos" else "gcc",
         "-dynamiclib" if target == "macos" else "-shared", "-fPIC", "-O2",
         ROOT / "ci/collision.c", "-o", ROOT / "release" /
         ("collision.dylib" if target == "macos" else "collision.so")])
    run([sys.executable, "-m", "twine", "check", *sorted((ROOT / "wheelhouse").glob("*.whl"))])
    source_bundle(target, records)


if __name__ == "__main__":
    main()
