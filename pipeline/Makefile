# The pipeline's own gate. The root Makefile's `make pipeline` (and so the
# repository's `make verify`) runs `verify` here; CI's pipeline job runs it
# through that target once #11 lands.
#
# `--frozen` everywhere after the lock check: a bare `uv run` or `uv sync`
# silently rewrites a stale uv.lock, which would repair the very drift
# `lock-check` exists to catch (CODE-QUALITY-STANDARD §2, CQ-09).

SHELL := bash

.PHONY: lock-check install lint format-check type test wheel verify fetch fetch-full build validate

lock-check:
	uv lock --check

install: lock-check
	uv sync --frozen --all-groups

lint:
	uv run --frozen ruff check src tests

format-check:
	uv run --frozen ruff format --check src tests

type:
	uv run --frozen mypy

# Coverage (branch, 85% floor) and the TODO/suppression hygiene test run as
# part of pytest; see [tool.pytest.ini_options] and tests/test_code_hygiene.py.
test:
	uv run --frozen pytest

# The package builds as a wheel through its hatchling backend (CQ-10). Every
# multi-command line sets errexit itself: macOS's make 3.81 has no .SHELLFLAGS.
wheel:
	set -euo pipefail; out="$$(mktemp -d)"; trap 'rm -rf "$$out"' EXIT; \
	uv build --wheel --out-dir "$$out"; \
	ls "$$out"/qtv_pipeline-*.whl

verify: install lint format-check type test wheel
	@echo "verify: lock, lint, format, types, tests, coverage and wheel green (no source contacted)"

fetch:
	uv run --frozen qtv fetch --cache .cache

fetch-full:
	uv run --frozen qtv fetch --cache .cache --full

build:
	uv run --frozen qtv build --cache .cache --out out

validate:
	uv run --frozen qtv validate out/snapshot.v1.json
