"""Strict ELF audit. Undefined weak references are audited as well as exports."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
import subprocess
import sys

ALLOWED_NEEDED = {"libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0",
                  "librt.so.1", "libutil.so.1", "libgcc_s.so.1", "ld-linux-x86-64.so.2"}
ALLOWED_WEAK = {"__gmon_start__", "_ITM_registerTMCloneTable", "_ITM_deregisterTMCloneTable"}
PRIVATE = re.compile(r"^(SSL_|OPENSSL_|OSSL_|CRYPTO_|EVP_|BIO_|X509_|ASN1_|OBJ_|RSA_|EC_|"
                     r"ENGINE_|RAND_|ERR_|BN_|PEM_|PKCS|DH_|DSA_|ZSTD_|ZLIB_|zlib|"
                     r"deflate|inflate|compress|uncompress|adler32|crc32|mysql_|mariadb_|ma_)")

def inspect_text(defined, undefined, dynamic, versions):
    exports = [line.split()[-1].split("@")[0] for line in defined.splitlines() if line.strip()]
    imports = [line.split()[-1] for line in undefined.splitlines() if line.strip()]
    needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)
    glibc = sorted({tuple(map(int, v.split("."))) for v in re.findall(r"GLIBC_(\d+\.\d+(?:\.\d+)?)", versions)})
    errors = []
    if sorted(exports) != ["PyInit__mysql"]:
        errors.append(f"Export allowlist violated: {exports}")
    if set(needed) - ALLOWED_NEEDED:
        errors.append(f"Unexpected shared libraries: {sorted(set(needed) - ALLOWED_NEEDED)}")
    if "RPATH" in dynamic or "RUNPATH" in dynamic:
        errors.append("Unexpected RPATH/RUNPATH in a private-static extension")
    if glibc and max(glibc) > (2, 28):
        errors.append(f"glibc floor exceeds 2.28: {max(glibc)}")
    for name in imports:
        base = name.split("@")[0]
        if PRIVATE.match(base):
            errors.append(f"Private dependency symbol unresolved (including weak refs): {name}")
        elif "@GLIBC_" in name or "@GCC_" in name:
            pass
        elif base.startswith(("Py", "_Py")) or base in ALLOWED_WEAK:
            pass
        else:
            errors.append(f"Unreviewed external symbol: {name}")
    return dict(exports=exports, needed=needed, undefined=imports,
                max_glibc=".".join(map(str, max(glibc))) if glibc else None, errors=errors)

def audit(path):
    def out(*args):
        return subprocess.check_output(args, text=True)
    return inspect_text(out("nm", "-D", "--defined-only", str(path)),
                        out("nm", "-D", "--undefined-only", str(path)),
                        out("readelf", "-dW", str(path)), out("readelf", "-VW", str(path)))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("extension", type=Path)
    p.add_argument("--output", type=Path)
    a = p.parse_args()
    result = audit(a.extension)
    result["file"] = str(a.extension)
    text = json.dumps(result, indent=2)
    print(text)
    if a.output:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(text + "\n")
    return bool(result["errors"])

if __name__ == "__main__":
    sys.exit(main())
