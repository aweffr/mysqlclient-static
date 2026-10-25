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
python -m pip install mysqlclient-static
```

### 替换 mysqlclient

两个分发包都提供 `MySQLdb`，应用依赖中应保留其中一个：

```bash
python -m pip uninstall -y mysqlclient
python -m pip install mysqlclient-static
```

如果其他依赖声明了 `mysqlclient`，仍需在应用的依赖配置中处理这一要求；
安装 `mysqlclient-static` 不会自动满足这个分发包名。

## 支持的环境

- Linux AMD64（x86-64），glibc 2.28 及以上。
- macOS ARM64（Apple Silicon），macOS 11 及以上。

pip 和 uv 会自动选择匹配当前 Python 和平台的 wheel（预编译安装包）。

| Python | mysqlclient 版本 | 安装包版本 |
|---|---|---|
| CPython 3.9 | 2.2.7 | 2.2.7.post3 |
| CPython 3.10–3.14 | 2.3.0 | 2.3.0.post3 |
| CPython 3.14t（自由线程版） | 2.3.0 | 2.3.0.post3 |

`2.3.0.post3` 表示 mysqlclient 2.3.0 的第 3 次打包修订。

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
不会自动提交事务。每个并发线程各用一个连接。

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

## 离线安装

离线安装时，从 [GitHub Releases](https://github.com/aweffr/mysqlclient-static/releases)
下载与 Python 版本和平台匹配的 wheel。例如，在 macOS ARM64 的 CPython 3.12
环境中运行：

```bash
python -m pip install ./mysqlclient_static-2.3.0.post3-cp312-cp312-macosx_11_0_arm64.whl
```

## 更多资料

wheel 内附中英文 README、`MySQLdb/AGENTS.md`、API 符号索引
`MySQLdb/api-symbols.json` 和 `MySQLdb/examples/` 中的示例。

- [agent 使用说明](https://github.com/aweffr/mysqlclient-static/blob/master/docs/agent-guide.md)：API、事务、连接生命周期，以及 Django 和 Celery 集成。
- [开发说明](https://github.com/aweffr/mysqlclient-static/blob/master/docs/development.md)：内置库版本、兼容基线、构建、测试和发布。

## 许可证与源码

本项目独立原创的代码、构建脚本、配置、文档和示例采用 MIT 许可证。
PyPI 的许可证元数据声明为 MIT。
上游源码及其衍生内容保留原有许可证，以及各组件的版权与许可声明。
每次 Release 都附带 `corresponding-source-*.tar.gz`，
包含原始源码、构建脚本、配置和来源记录。

详见[组件清单](https://github.com/aweffr/mysqlclient-static/blob/master/licenses/COMPONENTS.md)。
