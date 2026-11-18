# FC Squad Lab

Herramienta personal para resolver SBC de EA FC 27. Monorepo: API en Python (FastAPI + OR-Tools) en `apps/api`, web en Next.js 16.4.6 / React 19.3.0 (`apps/web`, puerto 3030) y una extensión de Chrome de solo lectura (`apps/extension`).

## Primera puesta en marcha

Requiere Python 3.13, `uv`, Node y Postgres.app 16. En este orden:

1. `make db-start` — arranca Postgres local (puerto 5544; no arranca solo tras reiniciar el Mac).
2. `make db-migrate` — crea las tablas.
3. Crear `apps/api/.env` (ignorado por git) a partir de `apps/api/.env.example` y poner un token propio, p. ej. `FCSL_IMPORT_TOKEN=un-secreto-largo` (`FCSL_HTTP_USER_AGENT` es opcional). Las variables de entorno le ganan al archivo.
4. `make api-dev` — API en `http://127.0.0.1:8787`.
5. `cd apps/web && npm install && npm run dev` — web en `http://localhost:3030`.
6. `make ext-build` y en Chrome (`chrome://extensions`, "Modo de desarrollador") → "Cargar descomprimida" → `apps/extension/dist`.
7. En las opciones de la extensión: URL del API (`http://localhost:8787`) y el mismo token del paso 3. "Probar conexión" debe responder bien.

**Desde el PC con Windows de la red de casa:** arrancar la API con `make api-dev API_HOST=0.0.0.0` (escucha en todas las interfaces del Mac) y en las opciones de la extensión usar `http://<IP-del-Mac>:8787`; Chrome pedirá permiso para ese host. Sin `API_HOST` la API solo acepta conexiones del propio Mac.

## Desarrollo

- Verificación completa antes de commitear: `make check` (API: `ruff check`, `ruff format --check` y `pytest` sin los lentos; web: `npm run lint` y `npm test`)
- Tests de la API: `make api-test`
- Servidor de la API (puerto 8787, `127.0.0.1` salvo `API_HOST=0.0.0.0`): `make api-dev`; lee `apps/api/.env` si existe
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
