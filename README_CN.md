# mysqlclient-static

[English](README.md) | 简体中文

为 Linux AMD64 和 macOS ARM64 提供自包含的 mysqlclient wheel。
安装后即可使用 `MySQLdb`，无需编译代码，也无需安装 MySQL/MariaDB
客户端库或认证插件。

本项目对 [mysqlclient](https://github.com/PyMySQL/mysqlclient) 进行打包。
Django 使用标准的 `django.db.backends.mysql` 后端。

## 安装

```bash
uv add mysqlclient-static
```

使用 pip：

```bash
python -m pip install --only-binary=:all: mysqlclient-static
```

离线安装时，从 [GitHub Releases](https://github.com/aweffr/mysqlclient-static/releases)
下载与 Python 版本和平台匹配的 wheel。例如，在 macOS ARM64 的 CPython 3.12
环境中运行：

```bash
python -m pip install --no-index \
  ./mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

### 替换 mysqlclient

两个分发包都提供 `MySQLdb`，应用依赖中应保留其中一个：

```bash
python -m pip uninstall -y mysqlclient
python -m pip install --only-binary=:all: mysqlclient-static
```

如果其他依赖声明了 `mysqlclient`，仍需在应用的依赖配置中处理这一要求；
安装 `mysqlclient-static` 不会自动满足这个分发包名。

## 支持版本

| Python | 上游 mysqlclient | 分发版本 | 平台 |
|---|---|---|---|
| CPython 3.9 | 2.2.7 | 2.2.7.post3 | Linux AMD64、macOS ARM64 |
| CPython 3.10–3.14 | 2.3.0 | 2.3.0.post3 | Linux AMD64、macOS ARM64 |
| CPython 3.14t（自由线程版） | 2.3.0 | 2.3.0.post3 | Linux AMD64、macOS ARM64 |

Linux wheel 的基线为 `manylinux_2_28_x86_64`。
macOS wheel 的目标为 `macosx_11_0_arm64`，支持 macOS 11 及以上系统。
Python 3.14t 使用单独的 `cp314-cp314t` wheel；每个并发线程各用一个连接。

wheel 内置 MariaDB Connector/C 3.4.11、OpenSSL 3.5.9、zlib 1.3.2 和
zstd 1.5.7。Linux 使用系统 glibc，macOS 使用系统库。

## 版本号与 wheel 文件名

分发版本由上游 mysqlclient 版本和本项目的打包修订号组成。
`2.3.0.post3` 表示 mysqlclient 2.3.0 的第 3 次打包修订。
更新内置库或打包方式时递增 `.postN`；上游升级时开启新的版本线，
例如 `2.3.1.post1`。

Python 和平台兼容性写在 wheel 文件名中：

```text
mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

| 部分 | 含义 |
|---|---|
| `2.3.0.post3` | 上游版本与打包修订号 |
| 第一个 `cp312` | CPython 3.12 |
| 第二个 `cp312` | CPython 3.12 的应用二进制接口（ABI） |
| `macosx_11_0_arm64` | macOS 11 及以上系统，ARM64 |

每个 GitHub Release 按分发版本归档，例如 `v2.3.0.post3`。
该版本包含 12 个 wheel，覆盖 6 个 Python 变体和两个平台。
`v2.2.7.post3` 包含 Python 3.9 的两个平台构件。
PyPI 与 GitHub Releases 提供相同的文件。

MySQL Server 的 8.0.46、8.4.13 等版本描述数据库兼容范围，
与 Python 驱动的版本号分别管理。

## 典型用法

在环境变量中设置 `DB_USER`、`DB_PASSWORD` 和 `DB_NAME`：

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

SQL 参数使用 `%s`，值单独传入。写操作需要显式调用 `commit()`，
异常时调用 `rollback()`。连接的 `with` 语句负责关闭连接，
不会自动提交事务。

### SQLAlchemy

SQLAlchemy 通过标准的
[`mysqldb` 方言](https://docs.sqlalchemy.org/en/21/dialects/mysql.html#module-sqlalchemy.dialects.mysql.mysqldb)
使用本包。安装两个依赖：

```bash
uv add mysqlclient-static sqlalchemy
```

连接 URL 使用 `mysql+mysqldb`。与上例一样，设置 `DB_USER`、`DB_PASSWORD`
和 `DB_NAME`；`DB_PORT` 默认为 3306：

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

同一个 engine 也可用于 SQLAlchemy ORM 的 `Session`。写操作可以放在
`engine.begin()` 代码块中，成功时提交，异常时回滚。

## 编程 agent 与示例

每个 wheel 都包含以下文件：

| 安装路径 | 内容 |
|---|---|
| `MySQLdb/README.md` | 英文安装说明与典型用法 |
| `MySQLdb/README_CN.md` | 内容对应的简体中文说明 |
| `MySQLdb/AGENTS.md` | API、事务、连接生命周期与集成说明 |
| `MySQLdb/api-symbols.json` | 从上游源码生成的签名、文档字符串和符号索引 |
| `MySQLdb/examples/` | 连接、事务、Django settings 和 Celery task 示例 |

```python
from importlib.resources import files

print(files("MySQLdb").joinpath("README.md").read_text())
print(files("MySQLdb").joinpath("api-symbols.json"))
```

[agent 使用说明](https://github.com/aweffr/mysqlclient-static/blob/master/docs/agent-guide.md)
和 `examples/` 与包一起维护，每条上游版本线独立生成符号索引。

兼容基线、内置库选型，以及面向开发者的构建、测试和发布说明见
[docs/development.md](https://github.com/aweffr/mysqlclient-static/blob/master/docs/development.md)。

## 许可证与源码

本项目独立原创的代码、构建脚本、配置、文档和示例采用 MIT 许可证。
PyPI 的许可证元数据声明为 MIT。
上游源码及其衍生内容保留原有许可证，以及各组件的版权与许可声明。
每次 Release 都附带 `corresponding-source-*.tar.gz`，
包含原始源码、构建脚本、配置和来源记录。

详见[组件清单](https://github.com/aweffr/mysqlclient-static/blob/master/licenses/COMPONENTS.md)。
