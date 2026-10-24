from pathlib import Path
import subprocess
import tempfile
import unittest

from ci.certificates import create


class CertificateTests(unittest.TestCase):
    def test_generated_chain_passes_strict_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            create(directory)
            p = Path(directory)
            result = subprocess.run(["openssl", "verify", "-x509_strict", "-CAfile", p / "ca.pem",
                                     p / "server.pem"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
