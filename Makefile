api-test:
	cd apps/api && uv run pytest

api-dev:
	cd apps/api && uv run uvicorn fcsl_api.main:app --port 8787 --reload

.PHONY: api-test api-dev
