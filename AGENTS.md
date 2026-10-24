# Repository guide for coding agents

This project distributes `mysqlclient-static`; applications import `MySQLdb`.
Read `README.md` for installation and `docs/agent-guide.md` for runtime semantics.

## Development

Use UV from the repository root:

```bash
uv sync --locked
uv run python -m unittest discover -s tests/unit -v
uv run ruff check .
```

The root project manages build tools and is not published. `ci/build_wheels.py`
stages upstream sources and changes distribution metadata; upstream runtime
versions remain unchanged. `versions.json` owns upstream and native versions.

`ci/symbols.py` generates the installed API index from each upstream source tree.
Examples in `examples/` and the consumer guide are copied into every wheel.

## Validation

Linux builds and E2E run on GitHub's AMD64 runners. macOS builds and native
E2E run on GitHub's ARM64 runners. `ci/plan.py` defines the required matrix;
`ci/report.py` records actual PASS, FAIL, NOT_RUN and EXCLUDED states.

The publish workflow uploads the tested wheels, installs them from PyPI with
pip and UV, and repeats database E2E. See `docs/development.md` for build and
release instructions.
