# FC Squad Lab

Herramienta personal para resolver SBC de EA FC 27. Monorepo: API en Python (FastAPI + OR-Tools) en `apps/api`, web en Next.js 16.4.6 / React 19.3.0 (`apps/web`, puerto 3030) y una extensión de Chrome de solo lectura (`apps/extension`).

## Desarrollo

- Verificación completa antes de commitear: `make check` (API: `ruff check`, `ruff format --check` y `pytest` sin los lentos; web: `npm run lint` y `npm test`)
- Tests de la API: `make api-test`
- Servidor de la API (puerto 8787): `make api-dev`
- Postgres local (Postgres.app 16, puerto 5544, usuario/clave/base `fcsl`; no arranca solo tras reiniciar): `make db-start` / `make db-stop`
- Migraciones: `make db-migrate` (`DATABASE_URL` por defecto `postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl`)
- Lint: `cd apps/api && uv run ruff check .`

Requiere Python 3.13 y `uv`.
- Web: `cd apps/web && npm run dev` (puerto 3030), tests `npm test`; la URL del API se configura con `NEXT_PUBLIC_API_URL` (por defecto `http://localhost:8787`)

## Extensión de Chrome (importar club y precios)

Observa pasivamente las respuestas que la web app de EA FC ya recibe (club, almacenamiento, lista de transferencias, observados y búsquedas manuales en el mercado) y las envía a la API local. No hace peticiones a EA ni envía cookies ni tokens de sesión.

1. `cd apps/extension && npm install && npm run build` (o `make ext-build`); genera `apps/extension/dist/`.
2. En Chrome: `chrome://extensions` → activar "Modo de desarrollador" → "Cargar descomprimida" → elegir `apps/extension/dist`.
3. Abrir las opciones de la extensión y configurar la URL del API (por defecto `http://localhost:8787`; si es una IP de la red de casa, Chrome pedirá permiso para ese host) y el token (el mismo `FCSL_IMPORT_TOKEN` de la API). "Probar conexión" llama a `GET /health`.
4. Navegar la web app de EA; los contadores de las opciones muestran lo enviado. La casilla "modo muestras" guarda respuestas crudas de `/ut/game/` en `/import/raw` (sin query string) para depurar.

Tests: `make ext-test`.
