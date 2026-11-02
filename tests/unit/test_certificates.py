from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci.certificates import create


class CertificateTests(unittest.TestCase):
    def test_generated_chain_passes_strict_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            create(directory)
            p = Path(directory)
            result = subprocess.run(["openssl", "verify", "-x509_strict", "-CAfile", p / "ca.pem",
                                     p / "server.pem"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_default_ca_extensions_are_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            inherited = p / "inherited.cnf"
            inherited.write_text("[req]\ndistinguished_name=dn\nx509_extensions=v3_ca\n"
                                 "[dn]\n[v3_ca]\nbasicConstraints=critical,CA:TRUE\n"
                                 "subjectKeyIdentifier=hash\n")
            with patch.dict(os.environ, OPENSSL_CONF=str(inherited)):
                create(p / "certs")
            result = subprocess.run(["openssl", "x509", "-in", p / "certs/ca.pem",
                                     "-noout", "-text"], capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.count("X509v3 Basic Constraints:"), 1)
            self.assertEqual(result.stdout.count("X509v3 Subject Key Identifier:"), 1)
