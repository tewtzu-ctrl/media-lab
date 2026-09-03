.PHONY: setup test lint format typecheck check doctor

setup:
	uv sync --group dev
	npm install --no-audit --no-fund

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy

check: lint typecheck test

doctor:
	uv run media-lab doctor
