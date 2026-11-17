check:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pytest
	cd apps/web && npm run lint && npm test

api-test:
	cd apps/api && uv run pytest

api-dev:
	cd apps/api && uv run uvicorn fcsl_api.main:app --port 8787 --reload

PG_BIN = /Applications/Postgres.app/Contents/Versions/16/bin
PG_DATA = $(HOME)/Library/Application Support/Postgres/var-16-fcsl

db-start:
	"$(PG_BIN)/pg_ctl" -D "$(PG_DATA)" -l "$(PG_DATA)/server.log" start

db-stop:
	"$(PG_BIN)/pg_ctl" -D "$(PG_DATA)" stop

db-migrate:
	cd apps/api && uv run alembic upgrade head

.PHONY: check api-test api-dev db-start db-stop db-migrate
