check:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
	cd apps/web && npm run lint && npm test
	cd apps/extension && npm run lint && npm test

ext-build:
	cd apps/extension && npm run build

ext-test:
	cd apps/extension && npm test

api-test:
	cd apps/api && uv run pytest

API_HOST ?= 127.0.0.1

api-dev:
	cd apps/api && uv run uvicorn fcsl_api.main:app --host $(API_HOST) --port 8787 --reload

PG_BIN = /Applications/Postgres.app/Contents/Versions/16/bin
PG_DATA = $(HOME)/Library/Application Support/Postgres/var-16-fcsl

db-start:
	"$(PG_BIN)/pg_ctl" -D "$(PG_DATA)" -l "$(PG_DATA)/server.log" start

db-stop:
	"$(PG_BIN)/pg_ctl" -D "$(PG_DATA)" stop

db-migrate:
	cd apps/api && uv run alembic upgrade head

sync-cards:
	cd apps/api && uv run python -m fcsl_api.ingest sync-cards $(ARGS)

sync-prices:
	cd apps/api && uv run python -m fcsl_api.ingest sync-prices $(ARGS)

sync-club-attributes:
	cd apps/api && uv run python -m fcsl_api.ingest sync-club-attributes $(ARGS)

squad-scan:
	cd apps/api && uv run python -m fcsl_api.squad scan $(ARGS)

data-status:
	cd apps/api && uv run python -m fcsl_api.ingest status

.PHONY: squad-scan sync-club-attributes check ext-build ext-test api-test api-dev db-start db-stop db-migrate sync-cards sync-prices data-status
