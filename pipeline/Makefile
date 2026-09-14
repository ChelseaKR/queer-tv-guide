.PHONY: install lint test verify fetch build validate

install:
	uv sync --all-groups

lint:
	uv run ruff check src tests

test:
	uv run pytest

verify: install lint test
	@echo "verify: lint + tests green (offline; no network calls made)"

fetch:
	uv run qtv fetch --cache .cache

fetch-full:
	uv run qtv fetch --cache .cache --full

build:
	uv run qtv build --cache .cache --out out

validate:
	uv run qtv validate out/snapshot.v1.json
