from pathlib import Path
import tempfile
import unittest

from ci.symbols import symbol_index


class SymbolIndexTests(unittest.TestCase):
    def test_public_api_signatures_aliases_and_native_methods(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "MySQLdb"
            package.mkdir()
            (package / "__init__.py").write_text('''
from ._mysql import Error
def Connect(*args, **kwargs):
    """Open a connection."""
connect = Connection = Connect
def _internal(): pass
class Cursor:
    def execute(self, query, args=None):
        """Execute a query."""
    def _private(self): pass
''')
            (package / "_mysql.c").write_text('''
static PyMethodDef _mysql_methods[] = {
    {"get_client_info", (PyCFunction)info, 0, NULL},
};
''')
            index = symbol_index(package)
        module = index["modules"][0]
        self.assertEqual(module["module"], "MySQLdb")
        symbols = {s["name"]: s for s in module["symbols"]}
        self.assertNotIn("_internal", symbols)
        self.assertEqual(symbols["Connect"]["signature"], "Connect(*args, **kwargs)")
        self.assertEqual(symbols["connect"]["target"], "Connect")
        self.assertEqual(symbols["Error"]["source"], "._mysql")
        self.assertEqual([m["name"] for m in symbols["Cursor"]["methods"]], ["execute"])
        self.assertEqual(symbols["Cursor"]["methods"][0]["signature"], "execute(self, query, args=None)")
        self.assertEqual(index["native_methods"]["MySQLdb._mysql"], ["get_client_info"])
