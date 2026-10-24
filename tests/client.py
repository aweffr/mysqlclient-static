"""Runs inside a clean runtime container against a real MySQL server."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
import ctypes.util
import importlib.metadata
from importlib.resources import files
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import sysconfig
import tempfile
from threading import Barrier
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
CERTS = Path(os.environ.get("CERTS_DIR", "/certs"))
sys.path.insert(0, str(ROOT / "tests/app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webapp.settings")

def gil_check():
    if not sysconfig.get_config_var("Py_GIL_DISABLED"):
        return None
    enabled = sys._is_gil_enabled()
    assert enabled is False, "The free-threaded interpreter must keep the GIL disabled"
    return enabled

def package_check():
    gil_before = gil_check()
    import MySQLdb
    gil_after = gil_check()
    try:
        importlib.metadata.version("mysqlclient")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise AssertionError("The upstream distribution must not be installed alongside mysqlclient-static")
    lock = json.loads((ROOT / "versions.json").read_text())
    version = importlib.metadata.version(lock["distribution"])
    py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        py += "t"
    expected = next(d["version"] for d in lock["upstream"].values() if py in d["python"])
    assert version == f"{expected}.post{lock['build_revision']}", version
    assert tuple(MySQLdb.version_info[:3]) == tuple(map(int, expected.split(".")))
    resources = files("MySQLdb")
    resources.joinpath("README.md").read_text()
    resources.joinpath("README_CN.md").read_text()
    resources.joinpath("AGENTS.md").read_text()
    symbols = json.loads(resources.joinpath("api-symbols.json").read_text())
    if sys.platform == "linux":
        assert not ctypes.util.find_library("mariadb"), "System libmariadb is present in test image"
        assert not ctypes.util.find_library("mysqlclient"), "System libmysqlclient is present"
    return {"distribution_version": version, "python": sys.version.split()[0],
            "client": MySQLdb._mysql.get_client_info(), "extension": MySQLdb._mysql.__file__,
            "api_modules": len(symbols["modules"]), "guide": str(resources.joinpath("README.md")),
            "free_threaded": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
            "gil_before_import": gil_before, "gil_after_import": gil_after}

def db_connect(*, tls=True, user=None, password=None, ca=None, compress=False):
    import MySQLdb
    ca = str(CERTS / "ca.pem") if ca is None else ca
    opts = dict(host="127.0.0.1", port=int(os.environ["DB_PORT"]),
                user=user or os.environ["DB_USER"], passwd=password or os.environ["DB_PASSWORD"],
                db=os.environ["DB_NAME"], charset="utf8mb4", connect_timeout=10,
                read_timeout=20, write_timeout=20)
    # mysqlclient enables compression when this keyword is present, even for 0.
    if compress:
        opts["compress"] = True
    if tls:
        opts.update(ssl={"ca": ca}, ssl_mode="VERIFY_IDENTITY")
    else:
        opts["ssl_mode"] = "DISABLED"
    return MySQLdb.connect(**opts)

def connection_probe(**kwargs):
    gil_check()
    conn = db_connect(**kwargs)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION(), CURRENT_USER(), CONNECTION_ID(), %s", ("中文🧪",))
            version, account, cid, text = cur.fetchone()
            assert version.split("-")[0] == os.environ["MYSQL_VERSION"], (version, os.environ["MYSQL_VERSION"])
            expected_user = kwargs.get("user") or os.environ["DB_USER"]
            assert account.split("@")[0] == expected_user
            assert text == "中文🧪"
            cur.execute("SHOW SESSION STATUS LIKE 'Ssl_cipher'")
            cipher = cur.fetchone()[1]
            assert bool(cipher) == kwargs.get("tls", True), cipher
            cur.execute("SHOW SESSION STATUS LIKE 'Compression'")
            assert cur.fetchone()[1] == ("ON" if kwargs.get("compress") else "OFF")
        return {"server": version, "account": account, "connection_id": cid, "cipher": cipher}
    finally:
        conn.close()

def rejection_probe():
    import MySQLdb
    for kwargs, code in [({"ca": str(CERTS / "wrong-ca.pem")}, 2026), ({"password": "definitely-incorrect"}, 1045)]:
        try:
            conn = db_connect(**kwargs)
        except MySQLdb.Error as exc:
            assert exc.args[0] == code, exc.args
        else:
            conn.close()
            raise AssertionError(f"Expected rejection {code}")

def crypto_coexistence():
    """Real CPython ssl handshake plus cryptography AEAD while MySQLdb is loaded."""
    import ssl
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from threading import Thread
    errors = []
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(str(CERTS / "server.pem"), str(CERTS / "server.key"))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(10)
    def echo():
        try:
            with listener:
                raw, _ = listener.accept()
                with server.wrap_socket(raw, server_side=True) as stream:
                    assert stream.recv(4) == b"ping"
                    stream.sendall(b"pong")
        except BaseException as exc:
            errors.append(str(exc))
    port = listener.getsockname()[1]
    worker = Thread(target=echo, daemon=True)
    worker.start()
    context = ssl.create_default_context(cafile=str(CERTS / "ca.pem"))
    with socket.create_connection(("127.0.0.1", port), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname="127.0.0.1") as stream:
            stream.sendall(b"ping")
            assert stream.recv(4) == b"pong"
    worker.join(12)
    assert not worker.is_alive() and not errors, errors
    cipher = AESGCM(AESGCM.generate_key(bit_length=128))
    nonce = os.urandom(12)
    assert cipher.decrypt(nonce, cipher.encrypt(nonce, b"private-static", b"aad"), b"aad") == b"private-static"
    return ssl.OPENSSL_VERSION

def driver_case():
    # Fresh server-side accounts guarantee an empty caching_sha2_password auth cache.
    cold = connection_probe()
    warm = connection_probe()
    assert cold["connection_id"] != warm["connection_id"]
    plain = connection_probe(tls=False, user=os.environ["DB_PLAIN_USER"])
    assert not plain["cipher"]
    compressed = connection_probe(compress=True)
    rejection_probe()
    barrier = Barrier(4)
    def concurrent_probe(_):
        barrier.wait(timeout=30)
        return connection_probe()
    with ThreadPoolExecutor(max_workers=4) as pool:
        parallel = list(pool.map(concurrent_probe, range(8)))
    assert len({r["connection_id"] for r in parallel}) == 8
    crypto = crypto_coexistence()
    env = dict(os.environ, DB_SSL_CA=str(CERTS / "ca.pem"))
    for name in ("basic.py", "transactions.py"):
        subprocess.run([sys.executable, str(files("MySQLdb").joinpath("examples", name))],
                       env=env, check=True, timeout=30)
    if sys.platform == "linux":
        maps = Path("/proc/self/maps").read_text()
        assert "libmariadb.so" not in maps and "libmysqlclient.so" not in maps
    return dict(cold=cold, warm=warm, plaintext_or_rsa=plain, compression=compressed,
                parallel_connections=8, stdlib_openssl=crypto, gil_after_checks=gil_check())

def setup_django():
    import django
    django.setup()
    from django.core.management import call_command
    call_command("check", verbosity=0)
    call_command("makemigrations", "probe", check=True, dry_run=True, verbosity=0)
    call_command("migrate", interactive=False, verbosity=1)
    from django.db import connection
    assert "probe_record" in connection.introspection.table_names()
    return django.get_version()

def rollback_migration():
    from django.core.management import call_command
    from django.db import connection
    call_command("migrate", "probe", "zero", interactive=False, verbosity=1)
    assert "probe_record" not in connection.introspection.table_names()
    connection.close()

def orm_case():
    version = setup_django()
    from django.db import transaction
    from probe.models import Record
    from probe.logic import crud_cycle, create_record
    result = crud_cycle(uuid.uuid4().hex)
    token = uuid.uuid4().hex
    try:
        with transaction.atomic():
            create_record(token)
            raise ValueError("intentional transaction rollback")
    except ValueError:
        pass
    assert not Record.objects.filter(token=token).exists()
    assert Record.objects.count() == 0
    rollback_migration()
    return dict(django=version, create_read_update_delete=result, transaction_rollback=True, migration_rollback=True)

@contextmanager
def child(args):
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            yield process
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            log.seek(0)
            print(log.read())

def http(method, path, body=None, expected=200):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request("http://127.0.0.1:18080" + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as exc:
        assert exc.code == expected, (exc.code, exc.read().decode())
        return json.loads(exc.read())
    with response:
        assert response.status == expected, response.status
        return json.load(response)

def wait_http(process):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Web server exited before readiness")
        try:
            if http("GET", "/health/")["ready"]:
                return
        except (OSError, ValueError):
            pass
        time.sleep(.25)
    raise TimeoutError("Web server not ready")

def http_crud(_):
    token = uuid.uuid4().hex
    created = http("POST", "/items/", {"token": token}, 201)
    pk = created["id"]
    assert http("GET", f"/items/{pk}/")["token"] == token
    assert http("PUT", f"/items/{pk}/", {"counter": 7})["counter"] == 7
    assert http("DELETE", f"/items/{pk}/")["deleted"]
    http("GET", f"/items/{pk}/", expected=404)
    return created

def web_case(mode):
    os.environ["CONN_MAX_AGE"] = "30" if mode == "wsgi" else "0"
    setup_django()
    from django.db import connections
    connections.close_all()
    if mode == "wsgi":
        args = [sys.executable, "-m", "gunicorn", "webapp.wsgi:application", "--bind", "127.0.0.1:18080",
                "--workers", "2", "--threads", "2", "--preload", "--timeout", "45"]
    else:
        args = [sys.executable, "-m", "uvicorn", "webapp.asgi:application", "--host", "127.0.0.1",
                "--port", "18080", "--workers", "2", "--lifespan", "off"]
    with child(args) as process:
        wait_http(process)
        with ThreadPoolExecutor(max_workers=8) as pool:
            rows = list(pool.map(http_crud, range(16)))
            if mode == "asgi":
                async_rows = list(pool.map(lambda _: http("POST", "/async-cycle/", {"token": uuid.uuid4().hex}), range(16)))
                assert all(x["counter"] == 1 for x in async_rows)
    from probe.models import Record
    assert Record.objects.count() == 0
    rollback_migration()
    return dict(server=mode, http_crud_cycles=len(rows), async_transaction_cycles=16 if mode == "asgi" else 0,
                worker_pids=sorted({r["pid"] for r in rows}))

def celery_case():
    setup_django()
    from webapp.celery_app import app
    from probe.tasks import database_cycle
    assert not app.conf.task_always_eager
    hostname = "mysqlclient-test@localhost"
    args = [sys.executable, "-m", "celery", "-A", "webapp.celery_app:app", "worker",
            "--pool=prefork", "--concurrency=2", "--max-tasks-per-child=2", "--loglevel=INFO",
            "--without-gossip", "--without-mingle", "--without-heartbeat", "--hostname", hostname,
            "--queues", os.environ["CELERY_QUEUE"]]
    with child(args) as process:
        deadline = time.monotonic() + 60
        while True:
            if process.poll() is not None:
                raise RuntimeError("Celery worker exited")
            if app.control.ping(destination=[hostname], timeout=1):
                break
            if time.monotonic() > deadline:
                raise TimeoutError("Celery worker not ready")
        futures = [database_cycle.apply_async(args=[uuid.uuid4().hex], queue=os.environ["CELERY_QUEUE"]) for _ in range(8)]
        rows = [f.get(timeout=120) for f in futures]
        for f in futures:
            f.forget()
        pids = {r["pid"] for r in rows}
        assert len(pids) >= 4, f"Worker recycling not observed: {pids}"
        assert os.getpid() not in pids
    from probe.models import Record
    assert Record.objects.count() == 0
    rollback_migration()
    return dict(tasks=8, pool="prefork", task_always_eager=False, worker_pids=sorted(pids), recycled=True)

def isolation_case():
    shim = ctypes.CDLL(str(ROOT / "release" / ("collision.dylib" if sys.platform == "darwin" else "collision.so")), mode=os.RTLD_NOW | os.RTLD_GLOBAL)
    old = sys.getdlopenflags()
    sys.setdlopenflags(os.RTLD_NOW | os.RTLD_GLOBAL)
    try:
        import MySQLdb
    finally:
        sys.setdlopenflags(old)
    assert MySQLdb._mysql.get_client_info() != "WRONG_GLOBAL_CLIENT"
    result = connection_probe()
    assert shim.collision_call_count() == 0
    return dict(global_conflict_ignored=True, result=result)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["driver", "distro", "orm", "wsgi", "asgi", "celery", "isolation"])
    args = p.parse_args()
    if args.mode == "isolation":
        # Import driver only after loading conflicting global symbols.
        result = isolation_case()
        meta = package_check()
    else:
        meta = package_check()
        if args.mode in ("driver", "distro"):
            result = driver_case()
        elif args.mode == "orm":
            result = orm_case()
        elif args.mode in ("wsgi", "asgi"):
            result = web_case(args.mode)
        else:
            result = celery_case()
    print("RESULT " + json.dumps({"metadata": meta, "checks": result}, ensure_ascii=False))

if __name__ == "__main__":
    main()
