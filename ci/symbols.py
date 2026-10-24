"""Index public symbols directly from the upstream source without importing C code."""
from __future__ import annotations

import ast
import re
from pathlib import Path


def symbol_index(package):
    package = Path(package)
    modules = []
    for path in sorted(package.rglob("*.py")):
        parts = path.relative_to(package.parent).with_suffix("").parts
        module = ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
        tree = ast.parse(path.read_text())
        symbols = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if node.name.startswith(("_", "test_")):
                    continue
                entry = dict(name=node.name, kind="class" if isinstance(node, ast.ClassDef) else "function",
                             line=node.lineno, doc=ast.get_docstring(node) or "")
                if isinstance(node, ast.FunctionDef):
                    entry["signature"] = f"{node.name}({ast.unparse(node.args)})"
                else:
                    entry["bases"] = [ast.unparse(base) for base in node.bases]
                    entry["methods"] = [dict(name=m.name, signature=f"{m.name}({ast.unparse(m.args)})",
                                             line=m.lineno, doc=ast.get_docstring(m) or "")
                                        for m in node.body if isinstance(m, ast.FunctionDef)
                                        and (not m.name.startswith("_") or m.name in ("__init__", "__enter__", "__exit__"))]
                symbols.append(entry)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        entry = dict(name=target.id, kind="alias" if isinstance(node.value, ast.Name) else "constant", line=node.lineno)
                        if isinstance(node.value, ast.Name):
                            entry["target"] = node.value.id
                        symbols.append(entry)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if not name.startswith("_"):
                        symbols.append(dict(name=name, kind="reexport", source="." * node.level + (node.module or ""), line=node.lineno))
        modules.append(dict(module=module, source=str(path.relative_to(package.parent)),
                            doc=ast.get_docstring(tree) or "", symbols=symbols))
    native = (package / "_mysql.c").read_text()
    native_tables = {}
    for table, name in (("_mysql_methods", "MySQLdb._mysql"),
                        ("_mysql_ConnectionObject_methods", "MySQLdb._mysql.connection"),
                        ("_mysql_ResultObject_methods", "MySQLdb._mysql.result")):
        match = re.search(re.escape(table) + r"\[\]\s*=\s*\{(.*?)\n\};", native, re.S)
        native_tables[name] = re.findall(r'\{\s*"([^\"]+)"', match.group(1)) if match else []
    return dict(import_package="MySQLdb", modules=modules, native_methods=native_tables)
