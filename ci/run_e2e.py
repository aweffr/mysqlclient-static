"""One Docker-backed end-to-end run, with independent cases and one aggregate report.

No production services are contacted. Containers are scoped to a random run ID.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from ci.certificates import create as create_certificates
from ci.common import ROOT, abi, matrix_config, python_request, run, wheel_for, write_json
from ci.plan import plan
from ci.report import render

class Runner:
    def __init__(self):
        self.c = matrix_config()
        self.rows = plan(self.c)
        self.prefix = "mcs-" + secrets.token_hex(4)
        self.password = secrets.token_hex(24)
        self.containers = []
        self.client_containers = []
        self.images = {}
        self.image_errors = {}
        self.servers = {}
        self.server_errors = {}
        self.work = ROOT / ".work" / self.prefix
        self.certs = self.work / "certs"
        self.logs = ROOT / "reports/e2e-logs"
        self.logs.mkdir(parents=True, exist_ok=True)
        self.inventory = []

    def redact(self, text):
        return str(text).replace(self.password, "[redacted]")

    def save(self):
        write_json(ROOT / "reports/results.json", self.rows)
        render(self.rows, ROOT / "reports")

    def image_id(self, image):
        data = json.loads(run(["docker", "image", "inspect", image]))[0]
        return dict(image=image, id=data["Id"], digests=data.get("RepoDigests", []))

    def admin(self, name, sql):
        return run(["docker", "exec", "-i", "-e", f"MYSQL_PWD={self.password}", name,
                    "mysql", "--protocol=socket", "-uroot", "--batch", "--skip-column-names"],
                   input=sql, timeout=60)

    def start_server(self, db):
        version = db["version"]
        name = f"{self.prefix}-mysql-{version.replace('.', '-')}"
        image = f"mysql:{version}"
        run(["docker", "pull", "--platform=linux/amd64", image], timeout=900,
            log=self.logs / f"pull-mysql-{version}.log")
        args = ["docker", "run", "-d", "--platform=linux/amd64", "--name", name,
                "--label", f"mysqlclient-static-run={self.prefix}",
                "-p", f"127.0.0.1:{db['port']}:3306", "-e", f"MYSQL_ROOT_PASSWORD={self.password}",
                "-v", f"{self.certs}:/certs:ro", image,
                "--ssl-ca=/certs/ca.pem", "--ssl-cert=/certs/server.pem", "--ssl-key=/certs/server.key",
                "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci",
                "--innodb-buffer-pool-size=128M", "--max-connections=100"]
        if db.get("enable_native"):
            args.append("--mysql-native-password=ON")
        run(args, timeout=60)
        # Record the name immediately, so readiness failures still get cleaned up.
        self.containers.append(name)
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            try:
                actual = self.admin(name, "SELECT VERSION();")
                # Initialization uses a temporary socket-only mysqld. Wait for final TCP too.
                import socket
                with socket.create_connection(("127.0.0.1", db["port"]), timeout=1) as s:
                    assert s.recv(128), "No MySQL handshake"
                if actual.split("-")[0] != version:
                    raise RuntimeError(f"Server tag/version mismatch: {version} vs {actual}")
                # The default remains caching_sha2_password, including 8.4 with native enabled.
                self.admin(name, f"CREATE USER 'default_auth_probe'@'%' IDENTIFIED BY '{self.password}';")
                plugin = self.admin(name, "SELECT plugin FROM mysql.user WHERE User='default_auth_probe' AND Host='%';")
                self.admin(name, "DROP USER 'default_auth_probe'@'%';")
                if plugin != "caching_sha2_password":
                    raise RuntimeError(f"Unexpected default authentication: {plugin}")
                self.servers[version] = dict(name=name, port=db["port"])
                self.inventory.append(self.image_id(image))
                return
            except Exception as exc:
                last = exc
                if "tag/version mismatch" in str(exc) or "Unexpected default" in str(exc):
                    raise
                time.sleep(2)
        raise RuntimeError(f"MySQL {version} readiness failed: {last}")

    def build_image(self, key, dockerfile, build_args):
        image = f"{self.prefix}-{key}"
        args = ["docker", "build", "--platform=linux/amd64", "-f", str(ROOT / dockerfile), "-t", image]
        for k, v in build_args.items():
            args += ["--build-arg", f"{k}={v}"]
        args.append(str(ROOT))
        try:
            run(args, timeout=900, log=self.logs / f"image-{key}.log")
            self.images[key] = image
            self.inventory.append(self.image_id(image))
        except Exception as exc:
            self.image_errors[key] = self.redact(exc)

    def setup(self):
        run(["docker", "info"], timeout=20)
        create_certificates(self.certs)
        # Four MySQL versions coexist on four loopback-only host ports.
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(self.start_server, db): db["version"] for db in self.c["mysql"]}
            for f in as_completed(futures):
                version = futures[f]
                try:
                    f.result()
                except Exception as exc:
                    self.server_errors[version] = self.redact(exc)
        redis_name = f"{self.prefix}-redis"
        run(["docker", "run", "-d", "--name", redis_name,
             "--label", f"mysqlclient-static-run={self.prefix}",
             "-p", "127.0.0.1:36379:6379", self.c["redis_image"],
             "redis-server", "--save", "", "--appendonly", "no"], timeout=300)
        self.containers.append(redis_name)
        self.inventory.append(self.image_id(self.c["redis_image"]))
        for py in self.c["python"]:
            self.build_image(abi(py), "ci/Dockerfile.runtime", {
                "PYTHON_VERSION": py.removesuffix("t"), "PYTHON_TARGET": python_request(py),
                "WHEEL": wheel_for(ROOT / "wheelhouse", py).name,
                "CRYPTOGRAPHY": self.c["crypto_tool"]})
        for p in self.c["django"]:
            base = self.images.get(abi(p["python"]))
            if not base:
                self.image_errors[p["id"]] = "Base Python runtime image failed"
                continue
            self.build_image(p["id"], "ci/Dockerfile.profile", {
                "BASE": base, "DJANGO": p["version"], "TOOLS": " ".join(self.c["runtime_tools"])})
        for d in self.c["distros"]:
            self.build_image(d["id"], "ci/Dockerfile.distro", {
                "BASE": d["image"], "DISTRO": d["id"],
                "WHEEL": wheel_for(ROOT / "wheelhouse", d["python"]).name,
                "CRYPTOGRAPHY": self.c["crypto_tool"]})
        write_json(ROOT / "reports/image-inventory.json", self.inventory)

    @contextmanager
    def case_environment(self, index, row):
        server = self.servers[row["mysql"]]
        dbname, user = f"case_{index:03d}", f"u{index:03d}"
        plain_user = user + "p"
        sql = f"""CREATE DATABASE `{dbname}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER '{user}'@'%' IDENTIFIED WITH {row['auth']} BY '{self.password}' REQUIRE SSL;
CREATE USER '{plain_user}'@'%' IDENTIFIED WITH {row['auth']} BY '{self.password}';
GRANT ALL ON `{dbname}`.* TO '{user}'@'%';
GRANT ALL ON `{dbname}`.* TO '{plain_user}'@'%';
SELECT User, plugin FROM mysql.user WHERE User IN ('{user}', '{plain_user}') ORDER BY User;
"""
        try:
            plugins = self.admin(server["name"], sql)
            assert set(plugins.splitlines()) == {f"{user}\t{row['auth']}", f"{plain_user}\t{row['auth']}"}, plugins
            yield {
                "DB_NAME": dbname, "DB_USER": user, "DB_PLAIN_USER": plain_user,
                "DB_PASSWORD": self.password, "DB_PORT": str(server["port"]),
                "MYSQL_VERSION": row["mysql"], "AUTH_PLUGIN": row["auth"],
                "CELERY_URL": "redis://127.0.0.1:36379/0", "CELERY_QUEUE": f"q{index}",
                "MARIADB_PLUGIN_DIR": "/does-not-exist", "OPENSSL_MODULES": "/does-not-exist",
            }
            row["server_plugin_verified"] = row["auth"]
        finally:
            self.admin(server["name"], f"DROP DATABASE IF EXISTS `{dbname}`; DROP USER IF EXISTS '{user}'@'%'; DROP USER IF EXISTS '{plain_user}'@'%';")

    def execute_case(self, index, row):
        key = row["django"] if row["suite"] in ("orm", "wsgi", "asgi", "celery", "distro") else abi(row["python"])
        if row["mysql"] in self.server_errors:
            raise RuntimeError(self.server_errors[row["mysql"]])
        if key in self.image_errors:
            raise RuntimeError(self.image_errors[key])
        with self.case_environment(index, row) as env:
            envfile = self.work / f"case-{index}.env"
            envfile.write_text("".join(f"{k}={v}\n" for k, v in env.items()))
            name = f"{self.prefix}-case-{index}"
            args = ["docker", "run", "--rm", "--network=host", "--name", name,
                    "--label", f"mysqlclient-static-run={self.prefix}",
                    "--env-file", envfile, "-v", f"{ROOT}:/repo:ro", "-v", f"{self.certs}:/certs:ro",
                    self.images[key], "python", "/repo/tests/client.py", row["suite"]]
            log = self.logs / f"case-{index:03d}.log"
            try:
                result = run(args, timeout=360, log=log)
                line = next(s[7:] for s in reversed(result.splitlines()) if s.startswith("RESULT "))
                row["checks"] = json.loads(line)
                row["log"] = str(log.relative_to(ROOT / "reports"))
            finally:
                if self.container_exists(name):
                    run(["docker", "rm", "-f", name], timeout=30)
                envfile.unlink(missing_ok=True)

    def container_exists(self, name):
        p = subprocess.run(["docker", "inspect", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p.returncode == 0

    def cleanup(self):
        # Restrict cleanup to this run's label. Never prune unrelated Docker resources.
        try:
            ids = run(["docker", "ps", "-aq", "--filter", f"label=mysqlclient-static-run={self.prefix}"], timeout=30).split()
            for name in self.containers:
                p = subprocess.run(["docker", "logs", name], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                (self.logs / f"{name}.log").write_text(self.redact(p.stdout))
            if ids:
                run(["docker", "rm", "-fv", *ids], timeout=120)
        except Exception as exc:
            (self.logs / "cleanup.log").write_text(self.redact(exc))
        import shutil
        shutil.rmtree(self.work, ignore_errors=True)

    def main(self):
        self.save()
        try:
            self.setup()
            for index, row in enumerate(self.rows):
                if row["status"] == "EXCLUDED":
                    continue
                started = time.monotonic()
                try:
                    self.execute_case(index, row)
                    row["status"] = "PASS"
                    row["reason"] = ""
                except Exception as exc:
                    row["status"] = "FAIL"
                    row["reason"] = self.redact(exc)
                row["seconds"] = round(time.monotonic() - started, 3)
                print(f"{row['status']:8s} {row['id']}", flush=True)
                self.save()
        except Exception as exc:
            error = self.redact(exc)
            for row in self.rows:
                if row["status"] == "NOT_RUN":
                    row["reason"] = f"Setup interrupted: {error}"
            print(error, file=sys.stderr)
        finally:
            self.cleanup()
            self.save()
        return 0 if render(self.rows, ROOT / "reports") else 1

if __name__ == "__main__":
    sys.exit(Runner().main())
