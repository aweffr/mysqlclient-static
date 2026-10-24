"""Run the shared driver and Django suites against native macOS services."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from ci.certificates import create
from ci.common import ROOT, abi, create_python_environment, run, wheel_for, write_json
from ci.run_e2e import Runner


class MacRunner(Runner):
    def __init__(self):
        os.environ["MCS_PLATFORM"] = "macos"
        super().__init__()
        self.processes = []
        self.service_logs = []

    def admin(self, name, sql):
        server = self.servers[name]
        return run([server["bin"] / "mysql", "--no-defaults", f"--socket={server['socket']}",
                    "-uroot", "--batch", "--skip-column-names"], input=sql, timeout=60)

    def service(self, args, label):
        log = open(self.logs / f"{label}.log", "w")
        process = subprocess.Popen([str(a) for a in args], stdout=log, stderr=subprocess.STDOUT)
        self.processes.append(process)
        self.service_logs.append(log)
        return process

    def start_server(self, db):
        version = db["version"]
        series = ".".join(version.split(".")[:2])
        binary = Path(run(["brew", "--prefix", f"mysql@{series}"])) / "bin"
        socket = self.work / f"mysql{series.replace('.', '')}.sock"
        data = self.work / f"mysql-{series}"
        self.servers[version] = dict(name=version, port=db["port"], bin=binary, socket=socket)
        run([binary / "mysqld", "--no-defaults", "--initialize-insecure", f"--datadir={data}"],
            timeout=180, log=self.logs / f"mysql-{version}-init.log")
        args = [binary / "mysqld", "--no-defaults", f"--datadir={data}",
                f"--socket={socket}", f"--port={db['port']}", "--bind-address=127.0.0.1",
                "--mysqlx=OFF", "--innodb-buffer-pool-size=128M",
                f"--ssl-ca={self.certs / 'ca.pem'}", f"--ssl-cert={self.certs / 'server.pem'}",
                f"--ssl-key={self.certs / 'server.key'}", "--character-set-server=utf8mb4",
                "--collation-server=utf8mb4_unicode_ci"]
        if db.get("enable_native"):
            args.append("--mysql-native-password=ON")
        server = self.service(args, f"mysql-{version}")
        deadline = time.monotonic() + 120
        while True:
            if server.poll() is not None:
                raise RuntimeError(f"MySQL {version} exited; see mysql-{version}.log")
            try:
                actual = self.admin(version, "SELECT VERSION();")
                break
            except RuntimeError:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"MySQL {version} readiness timed out")
                time.sleep(1)
        if actual.split("-")[0] != version:
            raise RuntimeError(f"Expected MySQL {version}, got {actual}")
        self.admin(version, f"CREATE USER 'default_probe'@'%' IDENTIFIED BY '{self.password}';")
        plugin = self.admin(version, "SELECT plugin FROM mysql.user WHERE User='default_probe';")
        assert plugin == "caching_sha2_password", plugin
        self.admin(version, "DROP USER 'default_probe'@'%';")
        return actual

    def setup(self):
        create(self.certs)
        versions = [self.start_server(db) for db in self.c["mysql"]]
        self.service(["redis-server", "--bind", "127.0.0.1", "--port", "36379",
                      "--save", "", "--appendonly", "no"], "redis")
        for py in self.c["python"]:
            self.environment(abi(py), py)
        for profile in self.c["django"]:
            self.environment(profile["id"], profile["python"], profile["version"])
        write_json(ROOT / "reports/image-inventory.json", {
            "mysql": versions, "redis": run(["redis-server", "--version"])})

    def environment(self, key, py, django=None):
        directory = self.work / "envs" / key
        try:
            create_python_environment(py, directory)
            python = directory / "bin/python"
            wheel = wheel_for(ROOT / "wheelhouse", py, "macosx")
            run(["uv", "pip", "install", "--python", python, "--only-binary", ":all:",
                 wheel, self.c["crypto_tool"]], timeout=300, log=self.logs / f"install-{key}.log")
            if django:
                run(["uv", "pip", "install", "--python", python, "--only-binary", ":all:",
                     f"Django=={django}", *self.c["runtime_tools"]], timeout=300,
                    log=self.logs / f"install-{key}.log")
            run(["uv", "pip", "check", "--python", python])
            self.images[key] = str(python)
        except Exception as exc:
            self.image_errors[key] = str(exc)

    def execute_case(self, index, row):
        key = row["django"] if row["suite"] in ("orm", "wsgi", "asgi", "celery") else abi(row["python"])
        if key in self.image_errors:
            raise RuntimeError(self.image_errors[key])
        with self.case_environment(index, row) as case_env:
            env = dict(os.environ, **case_env, CERTS_DIR=str(self.certs),
                       PYTHONPATH=f"{ROOT / 'tests/app'}:{ROOT}",
                       PYTHONFAULTHANDLER="1", PYTHONDONTWRITEBYTECODE="1")
            log = self.logs / f"case-{index:03d}.log"
            result = run([self.images[key], ROOT / "tests/client.py", row["suite"]],
                         cwd=ROOT / "tests/app", env=env, timeout=360, log=log)
            line = next(s[7:] for s in reversed(result.splitlines()) if s.startswith("RESULT "))
            row["checks"] = json.loads(line)
            row["log"] = str(log.relative_to(ROOT / "reports"))

    def cleanup(self):
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for log in self.service_logs:
            log.close()
        shutil.rmtree(self.work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(MacRunner().main())
