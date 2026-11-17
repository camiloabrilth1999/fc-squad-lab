# FC Squad Lab

Herramienta personal para resolver SBC de EA FC 27. Monorepo: API en Python (FastAPI + OR-Tools) en `apps/api` y web en Next.js (`apps/web`, pendiente).

## Desarrollo

- Tests de la API: `make api-test`
- Servidor de la API (puerto 8787): `make api-dev`
- Lint: `cd apps/api && uv run ruff check .`

Requiere Python 3.13 y `uv`.
