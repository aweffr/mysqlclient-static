# Component licensing and source inventory

This project's independent original code, build scripts, configuration,
documentation and examples use the MIT license in the root `LICENSE`.
Upstream sources, derived content and bundled components retain their own
licenses, obligations and copyright notices.

| Component | Selected version(s) | Upstream license / notices retained |
|---|---|---|
| mysqlclient | 2.2.7, 2.3.0 | GPL-2.0-or-later; original license files retained ([2.2.7](https://github.com/PyMySQL/mysqlclient/blob/v2.2.7/LICENSE), [2.3.0 metadata](https://github.com/PyMySQL/mysqlclient/blob/v2.3.0/pyproject.toml)) |
| MariaDB Connector/C | 3.4.11 | LGPL-2.1-or-later; [COPYING.LIB](https://github.com/mariadb-corporation/mariadb-connector-c/blob/v3.4.11/COPYING.LIB) and source-file notices retained |
| OpenSSL | 3.5.9 | Apache-2.0; [LICENSE.txt](https://github.com/openssl/openssl/blob/openssl-3.5.9/LICENSE.txt) and NOTICE retained when present |
| zlib | 1.3.2 | zlib license; [LICENSE](https://github.com/madler/zlib/blob/v1.3.2/LICENSE) retained |
| zstd | 1.5.7 | BSD-3-Clause selected; upstream also offers GPL-2.0. Both [LICENSE](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE) and [COPYING](https://github.com/facebook/zstd/blob/v1.5.7/COPYING) retained |

The package's PyPI license metadata is MIT. Build tooling copies the original
component notices into the wheel's license directory. Full original source
archives, exact source identity records, this build project, and test code
accompany each release. The project ships no closed-source component and does
not depend on proprietary link objects.

The root `LICENSE` contains the MIT text and its scope, and is copied into each
wheel as `LICENSES/mysqlclient-static-LICENSE`. Full copies of GPL-3.0,
Apache-2.0 and LGPL-2.1 are retained here. Original component-specific notices
come from the pinned upstream source archives during the build.
