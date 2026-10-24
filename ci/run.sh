#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --locked
uv run python -m unittest discover -s tests/unit -q
uv run python -m ci.fetch_sources
uv run python -m ci.build_wheels --platform linux
uv run python -m ci.run_e2e
