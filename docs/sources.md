# 版本与实现依据

核对日期：2026-10-24。版本值固定在 `versions.json`，以下页面用于审阅依据。

| 事实 | 官方来源 |
|---|---|
| Django 最新版、LTS 分支、各补丁版本 | https://www.djangoproject.com/download/ |
| Django 3.2 对 Python 的支持范围 | https://docs.djangoproject.com/en/3.2/faq/install/ |
| Django 5.2 的数据库要求 | https://docs.djangoproject.com/en/5.2/ref/databases/ |
| Django 6.1 最低 MySQL 8.4 | https://docs.djangoproject.com/en/6.1/ref/databases/ |
| mysqlclient 2.3.0 最低 Python 3.10 | https://pypi.org/project/mysqlclient/2.3.0/ |
| Python 3.9 使用的 mysqlclient 2.2.7 分支 | https://pypi.org/project/mysqlclient/2.2.7/ |
| MySQL 8.0.46 发布记录 | https://dev.mysql.com/doc/relnotes/mysql/8.0/en/news-8-0-46.html |
| MySQL 8.4.13 发布记录 | https://dev.mysql.com/doc/relnotes/mysql/8.4/en/news-8-4-13.html |
| MySQL 8.4 native 认证默认关闭与开关 | https://dev.mysql.com/doc/refman/8.4/en/native-pluggable-authentication.html |
| SHA-2 完整认证、缓存认证与传输方式 | https://dev.mysql.com/doc/refman/8.4/en/caching-sha2-pluggable-authentication.html |
| Connector/C 3.4.11 静态认证插件选项 | https://github.com/mariadb-corporation/mariadb-connector-c/blob/v3.4.11/plugins/auth/CMakeLists.txt |
| Connector/C 压缩插件选项 | https://github.com/mariadb-corporation/mariadb-connector-c/blob/v3.4.11/plugins/compress/CMakeLists.txt |
| manylinux 2.28 与解释器布局 | https://github.com/pypa/manylinux |
| GNU 链接器静态归档符号排除参数 | https://sourceware.org/binutils/docs/ld/Options.html |
| GNU 链接器导出白名单 | https://sourceware.org/binutils/docs/ld/VERSION.html |
| PyPI Trusted Publishing | https://docs.pypi.org/trusted-publishers/ |

Python 源码发布包的 SHA-256 在构建时同时与固定配置和 PyPI 元数据核对。原生源码的 Git 标签对象已固定；构建记录同时保存解析后的提交标识及 `git archive` 归档的 SHA-256。
