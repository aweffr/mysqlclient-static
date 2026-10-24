# Using mysqlclient-static with coding agents

## Package discovery

- Install distribution: `mysqlclient-static`.
- Import package: `MySQLdb`.
- Django backend: `django.db.backends.mysql`.
- Installed guides: `MySQLdb/README.md`, `MySQLdb/README_CN.md` and `MySQLdb/AGENTS.md`.
- Machine-readable API index: `MySQLdb/api-symbols.json`.
- Runnable and integration examples: `MySQLdb/examples/`.
- Native component versions: `MySQLdb/_static_build.json`.

Locate the installed material:

```python
from importlib.resources import files

package = files("MySQLdb")
print(package.joinpath("README.md").read_text())
print(package.joinpath("api-symbols.json"))
print(package.joinpath("examples"))
```

The symbol index is generated from the exact upstream version in each wheel.
It includes Python signatures, docstrings, source locations, public aliases,
reexports and native method names. Connection initialization options are in the
docstring of `MySQLdb.connections.Connection.__init__`. Methods implemented in
the C extension are listed under `native_methods`.

## Common symbols

| Symbol | Use |
|---|---|
| `MySQLdb.connect(**kwargs)` | Create a connection |
| `MySQLdb.connections.Connection` | Connection implementation |
| `connection.cursor()` | Create a tuple-row cursor |
| `MySQLdb.cursors.DictCursor` | Dictionary rows |
| `MySQLdb.cursors.SSCursor` | Stream a result set |
| `cursor.execute(sql, parameters)` | Execute a parameterized statement |
| `cursor.executemany(sql, rows)` | Execute repeated parameterized statements |
| `cursor.fetchone()` / `fetchall()` | Read result rows |
| `connection.commit()` / `rollback()` | Complete a transaction |
| `MySQLdb.IntegrityError` | Constraint violation |
| `MySQLdb.OperationalError` | Connection or server operation failure |

## Runtime semantics

Use `%s` placeholders and pass values separately. A one-value tuple is
`(value,)`. `DictCursor` changes returned rows, not SQL placeholder syntax.

Autocommit defaults to false. Commit writes explicitly. The connection's
context manager closes the connection; it does not automatically commit a
successful block. Cursor context managers close their cursor.

Each concurrent thread or process needs its own connection. Do not retain an
application-wide raw connection across worker forks. In a Django application,
use Django's ORM and connection lifecycle, including in Celery tasks.

Free-threaded CPython 3.14t uses a separate `cp314-cp314t` wheel. Importing
MySQLdb keeps the GIL disabled. Each concurrent thread still needs its own
connection.

This remains a synchronous driver. In Django ASGI code, use Django's async ORM
or adapt a synchronous transaction with `sync_to_async(thread_sensitive=True)`.
Use `CONN_MAX_AGE=0` for ASGI.

The distribution version contains `.postN`; `MySQLdb.version_info` reports the
original upstream version. Read `importlib.metadata.version("mysqlclient-static")`
for the installed distribution version.

Do not install `mysqlclient` alongside this package: both provide `MySQLdb`.
A dependency on the distribution name `mysqlclient` is a separate resolver
requirement and is not automatically satisfied by `mysqlclient-static`.

## Examples

Set `DB_USER`, `DB_PASSWORD` and `DB_NAME`. Optionally set `DB_HOST`, `DB_PORT`
and `DB_SSL_CA`.

```bash
python examples/basic.py
python examples/transactions.py
```

`django_settings.py` is an existing Django project's database configuration.
`celery_task.py` is a task for an existing Celery + Django application.
The transaction example uses a temporary table that disappears on disconnect.
