# Developer guide

Use this guide to check platform and dependency choices, or to build, test
and publish the package. Run development commands from a repository checkout.

## Choosing versions

The build combination below was reviewed on 2026-10-24 and is recorded in
`versions.json`. These are this project's fixed build inputs, rather than
minimum versions imposed by upstream mysqlclient.

### Linux compatibility

The supported Linux AMD64 baseline is glibc 2.28. A compatible CPython and an
x86-64 system with glibc 2.28 or later can use the same wheel across Linux
distributions. This covers Debian 10+, Ubuntu 20.04+ and Rocky Linux 8+.
The [manylinux project](https://github.com/pypa/manylinux#manylinux_2_28-almalinux-8-based)
documents the baseline and distribution compatibility.

This baseline retains Rocky Linux 8 support while using the maintained
AlmaLinux 8 build environment. A glibc 2.17 baseline would extend compatibility
to older systems and use an older build environment; a 2.34 baseline would
exclude Rocky Linux 8. Version 2.28 fits this project's Ubuntu, Debian and
Rocky target range with one Linux wheel per Python ABI.

The client library, TLS library, compression libraries and Python extension
are all compiled inside the manylinux 2.28 environment. The final audit rejects
glibc symbol requirements above 2.28. glibc itself comes from the operating
system. macOS ARM64 uses macOS system libraries and has no glibc requirement.

### Bundled libraries

| Library | Role | Version basis and official source |
|---|---|---|
| MariaDB Connector/C 3.4.11 | Implements the client protocol and MySQL-compatible C API used by mysqlclient, including authentication. | Stable release dated 2026-10-06 in the [official release list](https://mariadb.org/connector-c/all-releases/). The 3.4 line supports the authentication needed by the tested MySQL 8.0/8.4 servers. |
| OpenSSL 3.5.9 | Provides TLS and cryptographic operations for the client. | Patch release dated 2026-09-29 in the selected 3.5 LTS line. The [download list](https://openssl-library.org/source/) records 3.5.9; the [release policy](https://openssl-library.org/policies/releasestrat/) supports 3.5 until 2030-04-08. |
| zlib 1.3.2 | Provides zlib compression for the client protocol. | Release dated 2026-02-17. Its [official release notes](https://zlib.net/) include security-audit fixes and other corrections. |
| zstd 1.5.7 | Provides Zstandard compression support for Connector/C. | Published release with performance, stability and portability improvements, described in the [official release notes](https://github.com/facebook/zstd/releases/tag/v1.5.7). |

The choice combines stable upstream releases with a long-support TLS branch,
then fixes exact source versions so each build uses the same inputs. It is
validated as a complete client build against the database matrix below.

Connector/C's `mysql_native_password`, `caching_sha2_password` and
`sha256_password` authentication plugins are compiled into the client, as are
its compression plugins. OpenSSL supplies TLS and the cryptography used by
those authentication paths. Compression is used when requested and supported
by the connection; including both libraries does not enable it for every query.
See the [Connector/C plugin documentation](https://mariadb.com/docs/connectors/mariadb-connector-c/mariadb-connectorc-plugins)
for the plugin model.

### Installing and updating

These four libraries are linked into the Python extension. Applications install
the wheel without installing matching client, TLS or compression packages on
the host. Linux glibc and macOS system libraries remain operating-system
components.

Updating a system OpenSSL or Connector/C package does not replace the copy
inside this wheel. A bundled-library update is delivered by rebuilding the
wheel, running the binary audits and database tests, and increasing `.postN`.
Applications receive that update by upgrading `mysqlclient-static` and
redeploying it. The upstream driver version can stay the same while its
packaging revision increases, such as `2.3.0.post3` to `2.3.0.post4`.

## Development environment

Use Python 3.12 and UV:

```bash
uv sync --locked
uv run python -m unittest discover -s tests/unit -v
uv run ruff check .
rumdl check README.md README_CN.md docs/development.md
```

The root `pyproject.toml` manages development tools. The published packages are
prepared from upstream mysqlclient sources by `ci/build_wheels.py`.
`versions.json` records upstream versions, native libraries, packaging revision
and test services. `uv.lock` locks the development tools.

## Build wheels

GitHub Actions uses Linux AMD64 and macOS ARM64 runners. Each platform builds
its native libraries once, then cibuildwheel builds the seven Python wheels
through the `build[uv]` frontend and upstream setuptools backend.

```bash
gh workflow run verify.yml
```

To run the Linux build and tests on a Linux AMD64 machine with Docker:

```bash
bash ci/run.sh
```

Native dependencies are linked through explicit static archives. The Linux
build uses manylinux 2.28 and checks ELF dependencies, exports and glibc symbols.
The macOS build targets macOS 11 and checks Mach-O dependencies, exports,
architecture and deployment target. Both builds expose only the Python module
initialization function and run a symbol-conflict test.

Each wheel includes both READMEs, the consumer agent guide, examples, component
versions and an API index generated from that upstream source tree. The build
reads these resources from the final wheel before it can be released.

## Test matrix

| Suite | Linux AMD64 | macOS ARM64 |
|---|---:|---:|
| Driver | 56 | 28 |
| Django ORM | 34 | 18 |
| Gunicorn WSGI | 8 | 8 |
| Uvicorn ASGI | 8 | 8 |
| Celery prefork | 8 | 8 |
| Symbol-conflict injection | 4 | 4 |
| Ubuntu / Rocky runtime | 8 | 0 |
| Required total | 126 | 74 |

Linux tests MySQL 8.0.11, 8.0.27, 8.0.46 and 8.4.13. macOS runs native MySQL
8.0.46 and 8.4.13, each with its own data directory, socket and port. Homebrew
supplies the macOS test servers; the wheel's client libraries are built from
source independently.

Every applicable case runs with both `mysql_native_password` and
`caching_sha2_password`. Each case creates a fresh account and database.
The driver suite covers full and cached authentication, TLS, compression,
credential rejection, independent threaded connections, coexistence with
Python cryptography libraries and the installed runnable examples.

The Python targets include regular CPython 3.9–3.14 and free-threaded 3.14t.
The 3.14t driver cases check that the interpreter has `Py_GIL_DISABLED=1` and
keeps the GIL disabled before and after importing MySQLdb and running concurrent
database operations. They also exercise TLS and cryptography in that process.
Both pip and UV installation checks repeat the interpreter and GIL checks.

Django tests cover migrations, CRUD, field conversions, transaction rollback,
HTTP requests and Celery tasks with real Redis. Django 3.2 runs on Python
3.9/3.10. Django 6.1 requires MySQL 8.4, so its MySQL 8.0 combinations are
reported as `EXCLUDED`: six on Linux and two on macOS. Celery uses a prefork
pool; the macOS test application explicitly selects the fork start method.

The exact case list comes from `ci/plan.py`:

```bash
uv run python -m ci.plan
MCS_PLATFORM=macos uv run python -m ci.plan
```

Reports include Markdown, HTML, JSON and JUnit files, with actual versions and
case logs. `FAIL` and `NOT_RUN` prevent release; `EXCLUDED` does not count as a
passed test. Download `reports-linux` or `reports-macos` from Actions. Successful
wheel and source bundles are in `tested-linux` and `tested-macos`.

## Publishing

The `Publish` workflow builds and tests both platforms, creates one GitHub
Release per distribution version, then uploads those same wheel files to PyPI.
After upload, fresh runners install each Python ABI with pip and UV, read the
installed guides, and repeat database E2E using wheels downloaded from PyPI.

The batch includes two version lines. With `build_revision=3`:

| Upstream | Distribution version | GitHub Release tag | Wheel count |
|---|---|---|---:|
| 2.2.7 | 2.2.7.post3 | v2.2.7.post3 | 2 |
| 2.3.0 | 2.3.0.post3 | v2.3.0.post3 | 12 |

Release assets include wheels, both READMEs, source bundles and build inventories.
The Release body lists Python versions and platforms and gives an offline
installation command. Native library and packaging updates increase the
packaging revision. An upstream update starts a new version line. The
application's `MySQLdb.version_info` keeps the upstream runtime version.

Configure PyPI Trusted Publishing for this repository:

| Field | Value |
|---|---|
| Project name | mysqlclient-static |
| Owner | aweffr |
| Repository | mysqlclient-static |
| Workflow filename | release.yml |
| GitHub Environment | pypi |

Use a Pending Publisher for a new project, or add a publisher under an existing
project's Publishing settings. The workflow uses OIDC credentials provided by
GitHub Actions. No long-lived PyPI token is needed.

Run the workflow manually, or push a batch build tag:

```bash
gh workflow run release.yml
# Or, for packaging revision 3:
git tag build-r3
git push origin build-r3
```

The workflow creates the versioned Release tags from the tested commit.
PyPI releases are immutable: change `build_revision` before publishing changed
files. PyPI also rejects new files for releases older than 14 days, so prepare
all platform wheels together.

The published wheels can be audited and retested independently with:

```bash
gh workflow run check-index.yml
```

The standalone index installation check is:

```bash
uv run python -m ci.check_index --index pypi
```

Monthly upstream checks report available versions. Updating `versions.json`
starts the normal build, audit and test process.

## Build structure and source

`ci/fetch_sources.py` fetches the configured upstream sources on the runner.
`ci/build_native.sh` compiles the static dependencies. `ci/build_wheels.py`
prepares metadata, builds wheels, audits them and creates source bundles.
`ci/run_e2e.py` and `ci/run_macos.py` run the shared application tests.
`ci/release.py` groups the tested wheels by version for GitHub Releases.

Source bundles contain original upstream archives, this repository's build
scripts, tests, documentation, configuration and source records.

- [Component licenses](../licenses/COMPONENTS.md)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [UV publishing](https://docs.astral.sh/uv/guides/integration/github/)
- [PyPI upload window](https://blog.pypi.org/posts/2026-07-22-releases-now-reject-new-files-after-14-days/)
