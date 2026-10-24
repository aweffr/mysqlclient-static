"""Ephemeral test-only CA and server certificates, generated anew for each run."""
from pathlib import Path
from ci.common import run

def create(directory):
    p = Path(directory)
    p.mkdir(parents=True, exist_ok=True)
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "2",
         "-subj", "/CN=mysqlclient-static-test-CA", "-keyout", p / "ca.key", "-out", p / "ca.pem",
         "-addext", "basicConstraints=critical,CA:TRUE",
         "-addext", "keyUsage=critical,keyCertSign,cRLSign",
         "-addext", "subjectKeyIdentifier=hash"])
    run(["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-sha256", "-subj", "/CN=localhost",
         "-keyout", p / "server.key", "-out", p / "server.csr"])
    (p / "server.ext").write_text("subjectAltName=DNS:localhost,DNS:127.0.0.1,IP:127.0.0.1\n"
        "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
        "extendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
    run(["openssl", "x509", "-req", "-sha256", "-days", "2", "-in", p / "server.csr",
         "-CA", p / "ca.pem", "-CAkey", p / "ca.key", "-CAcreateserial", "-extfile", p / "server.ext",
         "-out", p / "server.pem"])
    run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256", "-days", "2",
         "-subj", "/CN=wrong-test-CA", "-keyout", p / "wrong-ca.key", "-out", p / "wrong-ca.pem"])
    # Generated fixtures only; MySQL containers run under different numeric UIDs.
    for f in p.iterdir():
        f.chmod(0o644)
