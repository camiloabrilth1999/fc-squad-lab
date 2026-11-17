# FC Squad Lab

Herramienta personal para resolver SBC de EA FC 27. Monorepo: API en Python (FastAPI + OR-Tools) en `apps/api` y web en Next.js 16.4.6 / React 19.3.0 (`apps/web`, puerto 3030).

## Desarrollo

- Verificación completa antes de commitear: `make check` (API: `ruff check`, `ruff format --check` y `pytest` sin los lentos; web: `npm run lint` y `npm test`)
- Tests de la API: `make api-test`
- Servidor de la API (puerto 8787): `make api-dev`
- Postgres local (Postgres.app 16, puerto 5544, usuario/clave/base `fcsl`; no arranca solo tras reiniciar): `make db-start` / `make db-stop`
- Migraciones: `make db-migrate` (`DATABASE_URL` por defecto `postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl`)
- Lint: `cd apps/api && uv run ruff check .`

Requiere Python 3.13 y `uv`.
- Web: `cd apps/web && npm run dev` (puerto 3030), tests `npm test`; la URL del API se configura con `NEXT_PUBLIC_API_URL` (por defecto `http://localhost:8787`)
