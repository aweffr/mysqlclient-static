# mysqlclient-static

English | [简体中文](README_CN.md)

Self-contained mysqlclient wheels for Linux AMD64 and macOS ARM64. Install a
wheel and use `MySQLdb` without compiling code or installing MySQL/MariaDB
client libraries or authentication plugins.

This project packages [mysqlclient](https://github.com/PyMySQL/mysqlclient).
Django uses its standard `django.db.backends.mysql` backend.

## Installation

```bash
uv add mysqlclient-static
```

With pip:

```bash
python -m pip install mysqlclient-static
```

### Replacing mysqlclient

Both distributions provide `MySQLdb`. Keep one in your application dependencies:

```bash
python -m pip uninstall -y mysqlclient
python -m pip install mysqlclient-static
```

A dependency declared as `mysqlclient` still needs to be handled in your
application's dependency configuration; installing `mysqlclient-static` does
not satisfy that distribution name.

## Supported environments

- Linux AMD64 (x86-64), glibc 2.28 or later.
- macOS ARM64 (Apple Silicon), macOS 11 or later.

pip and uv automatically select the wheel (prebuilt package) matching your
Python version and platform.

| Python | mysqlclient version | Package version |
|---|---|---|
| CPython 3.9 | 2.2.7 | 2.2.7.post3 |
| CPython 3.10–3.14 | 2.3.0 | 2.3.0.post3 |
| CPython 3.14t (free-threaded) | 2.3.0 | 2.3.0.post3 |

`2.3.0.post3` means mysqlclient 2.3.0, packaging revision 3.

## Typical usage

Set `DB_USER`, `DB_PASSWORD` and `DB_NAME` in your environment:

```python
import os
import MySQLdb
from MySQLdb.cursors import DictCursor

with MySQLdb.connect(
    host="127.0.0.1",
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.environ["DB_NAME"],
    charset="utf8mb4",
) as connection:
    with connection.cursor(DictCursor) as cursor:
        cursor.execute("SELECT %s AS message", ("你好，MySQL",))
        print(cursor.fetchone())
```

Use `%s` placeholders and pass values separately. Commit writes explicitly with
`commit()` and call `rollback()` on failure. A connection's `with` block closes
the connection; it does not commit the transaction automatically.
Each concurrent thread needs its own connection.

### SQLAlchemy

SQLAlchemy uses this package through its standard
[`mysqldb` dialect](https://docs.sqlalchemy.org/en/21/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb).
Install both packages:

```bash
uv add mysqlclient-static sqlalchemy
```

Use `mysql+mysqldb` in the connection URL. Set `DB_USER`, `DB_PASSWORD` and
`DB_NAME` as in the example above; `DB_PORT` defaults to 3306:

```python
import os
from sqlalchemy import URL, create_engine, text

url = URL.create(
    "mysql+mysqldb",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host="127.0.0.1",
    port=int(os.environ.get("DB_PORT", "3306")),
    database=os.environ["DB_NAME"],
    query={"charset": "utf8mb4"},
)
engine = create_engine(url)

with engine.connect() as connection:
    message = connection.execute(
        text("SELECT :message AS message"), {"message": "你好，MySQL"}
    ).scalar_one()
    print(message)

engine.dispose()
```

The same engine works with SQLAlchemy ORM `Session`. Use `engine.begin()`
for a block that commits writes on success and rolls back on an exception.

## Offline installation

For offline installation, download the wheel matching your Python version and
platform from [GitHub Releases](https://github.com/aweffr/mysqlclient-static/releases).
For example, with CPython 3.12 on macOS ARM64:

```bash
python -m pip install ./mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

## Further reading

Each wheel includes both READMEs, `MySQLdb/AGENTS.md`, the API symbol index
`MySQLdb/api-symbols.json`, and examples in `MySQLdb/examples/`.

- [Agent guide](https://github.com/aweffr/mysqlclient-static/blob/master/docs/agent-guide.md):
  API, transactions, connection lifecycle, and Django and Celery integration.
- [Developer guide](https://github.com/aweffr/mysqlclient-static/blob/master/docs/development.md):
  bundled library versions, compatibility baselines, building, testing and
  publishing.

## License and source

This project's independent original code, build scripts, configuration,
documentation and examples use the MIT license. The package's PyPI license
metadata is MIT. Upstream sources and derived content retain their original
licenses, with component copyright and license notices retained.
Each Release includes `corresponding-source-*.tar.gz` with the original sources,
build scripts, configuration and source records.

See the [component list](https://github.com/aweffr/mysqlclient-static/blob/master/licenses/COMPONENTS.md).
