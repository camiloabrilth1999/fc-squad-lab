# FC Squad Lab

Herramienta personal para resolver SBC de EA FC 27. Monorepo: API en Python (FastAPI + OR-Tools) en `apps/api` y web en Next.js 16.4.6 / React 19.3.0 (`apps/web`, puerto 3030).

## Desarrollo

- Tests de la API: `make api-test`
- Servidor de la API (puerto 8787): `make api-dev`
- Lint: `cd apps/api && uv run ruff check .`

Requiere Python 3.13 y `uv`.
- Web: `cd apps/web && npm run dev` (puerto 3030), tests `npm test`; la URL del API se configura con `NEXT_PUBLIC_API_URL` (por defecto `http://localhost:8787`)
