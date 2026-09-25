.PHONY: help infra-up infra-down test lint typecheck format check

help:
	@echo "LBOE bootstrap commands"
	@echo "  make infra-up    Start PostgreSQL and Redis"
	@echo "  make infra-down  Stop local infrastructure"
	@echo "  make test        Run tests (after Sprint 1 setup)"
	@echo "  make lint        Run Ruff (after Sprint 1 setup)"
	@echo "  make typecheck   Run mypy (after Sprint 1 setup)"
	@echo "  make check       Run lint + typecheck + test"

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down

test:
	pytest

lint:
	ruff check .

typecheck:
	mypy apps packages integrations tests

format:
	ruff format .

check: lint typecheck test
