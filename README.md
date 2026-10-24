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
python -m pip install --only-binary=:all: mysqlclient-static
```

For offline installation, download the wheel matching your Python version and
platform from [GitHub Releases](https://github.com/aweffr/mysqlclient-static/releases).
For example, with CPython 3.12 on macOS ARM64:

```bash
python -m pip install --no-index \
  ./mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

### Replacing mysqlclient

Both distributions provide `MySQLdb`. Keep one in your application dependencies:

```bash
python -m pip uninstall -y mysqlclient
python -m pip install --only-binary=:all: mysqlclient-static
```

A dependency declared as `mysqlclient` still needs to be handled in your
application's dependency configuration; installing `mysqlclient-static` does
not satisfy that distribution name.

## Supported versions

| Python | Upstream mysqlclient | Distribution version | Platforms |
|---|---|---|---|
| CPython 3.9 | 2.2.7 | 2.2.7.post3 | Linux AMD64, macOS ARM64 |
| CPython 3.10–3.14 | 2.3.0 | 2.3.0.post3 | Linux AMD64, macOS ARM64 |
| CPython 3.14t (free-threaded) | 2.3.0 | 2.3.0.post3 | Linux AMD64, macOS ARM64 |

Linux wheels use the `manylinux_2_28_x86_64` baseline. macOS wheels target
`macosx_11_0_arm64` (macOS 11 or later). Python 3.14t uses a separate
`cp314-cp314t` wheel. Each concurrent thread needs its own connection.

The wheels contain MariaDB Connector/C 3.4.11, OpenSSL 3.5.9, zlib 1.3.2 and
zstd 1.5.7. Linux uses the system glibc; macOS uses its system libraries.

## Version numbers and wheel names

The distribution version is the upstream mysqlclient version followed by this
project's packaging revision: `2.3.0.post3` means mysqlclient 2.3.0, packaging
revision 3. Updates to the bundled libraries or packaging increase `.postN`;
an upstream update starts a new version line, such as `2.3.1.post1`.

Python and platform compatibility are recorded in the wheel filename:

```text
mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

| Part | Meaning |
|---|---|
| `2.3.0.post3` | Upstream version and packaging revision |
| First `cp312` | CPython 3.12 |
| Second `cp312` | CPython 3.12 application binary interface (ABI) |
| `macosx_11_0_arm64` | macOS 11 or later, ARM64 |

Each GitHub Release groups all wheels for one distribution version under a tag
such as `v2.3.0.post3`. That version has 12 wheels: six Python variants across
two platforms. `v2.2.7.post3` has two wheels for Python 3.9. PyPI and GitHub
Releases distribute the same files.

MySQL Server versions such as 8.0.46 and 8.4.13 describe database compatibility;
they are separate from the Python driver's version.

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

## Coding agents and examples

Every wheel includes these files:

| Installed path | Contents |
|---|---|
| `MySQLdb/README.md` | English installation guide and typical usage |
| `MySQLdb/README_CN.md` | The same guide in Simplified Chinese |
| `MySQLdb/AGENTS.md` | API, transactions, connection lifecycle and integration |
| `MySQLdb/api-symbols.json` | Signatures, docstrings and symbols from the upstream source |
| `MySQLdb/examples/` | Connection, transaction, Django settings and Celery task examples |

```python
from importlib.resources import files

print(files("MySQLdb").joinpath("README.md").read_text())
print(files("MySQLdb").joinpath("api-symbols.json"))
```

The [agent guide](https://github.com/aweffr/mysqlclient-static/blob/master/docs/agent-guide.md)
and `examples/` are maintained with the package. Each upstream version gets its
own symbol index.

Compatibility baselines, bundled-library choices, and instructions for
building, testing and publishing are in
[docs/development.md](https://github.com/aweffr/mysqlclient-static/blob/master/docs/development.md).

## License and source

This project's independent original code, build scripts, configuration,
documentation and examples use the MIT license. The package's PyPI license
metadata is MIT. Upstream sources and derived content retain their original
licenses, with component copyright and license notices retained.
Each Release includes `corresponding-source-*.tar.gz` with the original sources,
build scripts, configuration and source records.

See the [component list](https://github.com/aweffr/mysqlclient-static/blob/master/licenses/COMPONENTS.md).
