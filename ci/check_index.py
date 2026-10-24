"""Install and audit every published ABI, then download wheels for E2E."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ci.audit import audit as audit_linux
from ci.audit_macos import audit as audit_macos
from ci.common import ROOT, abi, config, create_python_environment, run, upstream_for, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", choices=["pypi", "testpypi"], required=True)
    target = parser.parse_args().index
    url = "https://pypi.org/simple" if target == "pypi" else "https://test.pypi.org/simple"
    c = config()
    wheels = ROOT / "wheelhouse"
    wheels.mkdir(exist_ok=True)
    records = []
    for py in c["python"]:
        upstream = upstream_for(py)["version"]
        version = f"{upstream}.post{c['build_revision']}"
        spec = f"{c['distribution']}=={version}"
        for installer in ("pip", "uv"):
            env = ROOT / ".work/index-envs" / f"{abi(py)}-{installer}"
            create_python_environment(py, env)
            python = env / "bin/python"
            if installer == "pip":
                run([python, "-m", "pip", "install", "--no-cache-dir", "--no-deps",
                     "--only-binary=:all:", "--index-url", url, spec], timeout=300)
                run([python, "-m", "pip", "check"])
                run([python, "-m", "pip", "download", "--no-cache-dir", "--no-deps",
                     "--only-binary=:all:", "--index-url", url, "--dest", wheels, spec], timeout=300)
            else:
                run(["uv", "pip", "install", "--python", python, "--no-cache", "--no-deps",
                     "--only-binary", ":all:", "--index-url", url, spec], timeout=300)
                run(["uv", "pip", "check", "--python", python])
            probe = (
                "import importlib.metadata as m,json,sys,sysconfig; from importlib.resources import files; "
                f"assert bool(sysconfig.get_config_var('Py_GIL_DISABLED')) == {py.endswith('t')!r}; "
                "gil_before = sys._is_gil_enabled() if sysconfig.get_config_var('Py_GIL_DISABLED') else None; "
                "assert gil_before is not True; "
                "import MySQLdb; "
                "gil_after = sys._is_gil_enabled() if sysconfig.get_config_var('Py_GIL_DISABLED') else None; "
                "assert gil_after is not True; "
                f"assert m.version({c['distribution']!r}) == {version!r}; "
                f"assert m.metadata({c['distribution']!r})['License-Expression'] == 'MIT'; "
                f"assert tuple(MySQLdb.version_info[:3]) == {tuple(map(int, upstream.split('.')))!r}; "
                "files('MySQLdb').joinpath('README.md').read_text(); "
                "files('MySQLdb').joinpath('README_CN.md').read_text(); "
                "print(json.dumps({'version':m.version('mysqlclient-static'),"
                "'client':MySQLdb._mysql.get_client_info(),'extension':MySQLdb._mysql.__file__,"
                "'gil_before_import':gil_before,'gil_after_import':gil_after}))")
            result = run([python, "-I", "-c", probe], cwd=env)
            record = dict(python=py, installer=installer, index=target, **json.loads(result))
            if installer == "pip":
                record["audit"] = (audit_macos if sys.platform == "darwin" else audit_linux)(Path(record["extension"]))
                if record["audit"]["errors"]:
                    raise RuntimeError(f"Published wheel audit failed: {record['audit']['errors']}")
            records.append(record)
            write_json(ROOT / "reports/index-installs.json", records)
    print(f"Verified {len(records)} isolated installations from {target}")


if __name__ == "__main__":
    main()
