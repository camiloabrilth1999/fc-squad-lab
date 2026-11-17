# FC Squad Lab — guía para Claude

Proyecto personal de Camilo: web local para EA FC 27 Ultimate Team (solver de SBC con su club, constructor de plantillas, evoluciones, objetivos). Se desarrolla en **dos máquinas** (Mac y PC Windows con WSL2/Ubuntu) sincronizadas por el repo privado de GitHub. Leer primero `README.md`, el diseño `docs/superpowers/specs/2026-11-16-fc-squad-lab-design.md` y los planes en `docs/superpowers/plans/`.

## Reglas de trabajo

- Responder **siempre en español**.
- Commits **sin** línea `Co-Authored-By`.
- Mostrar el diff y esperar el OK de Camilo antes de hacer push, merge a `main` o cualquier despliegue.
- Si preguntaste "¿lo corrijo?", no cambies nada hasta que diga que sí.
- Al empezar en una máquina: `git pull`. Antes de cambiar de máquina: dejar todo commiteado y subido.
- Integración: rebase sobre `main` (no merges de `main` hacia la rama).

## Dos máquinas

- Cada máquina tiene **su propia** base de datos, `apps/api/.env` (token `FCSL_IMPORT_TOKEN` propio, nunca mostrarlo en el chat), caché (`apps/api/var/`) y `apps/extension/dist/`. Nada de eso va al repo.
- Cartas y precios se rellenan en cada máquina con `make sync-cards` y `make sync-prices` (~30 min en total).
- La extensión de cada máquina apunta a su propio API (`http://localhost:8787`).
- Mac: Postgres.app 16 en `/Applications/Postgres.app/Contents/Versions/16/bin`, cluster en `~/Library/Application Support/Postgres/var-16-fcsl`, sin Docker ni Homebrew en este usuario.
- Windows: trabajar **dentro de WSL2 (Ubuntu)**, en `~/code/fc-squad-lab`, no en `/mnt/c`. Postgres 16 de apt; ajustar `PG_BIN`/`PG_DATA` del Makefile por variable (`make db-start PG_BIN=... PG_DATA=...`) en vez de cambiar los valores del Mac.

## Puertos y stack

- API FastAPI 8787, web Next.js 3030, Postgres 5544 (rol/db `fcsl`/`fcsl`).
- API: Python 3.13 + `uv`, Pydantic v2, SQLAlchemy 2, Alembic, OR-Tools CP-SAT. **Solo la API PEP8 de OR-Tools** (los métodos camelCase obsoletos como `.Proto()` corrompen el modelo y tumban Python).
- Web: Next.js 16, React 19, Tailwind, Vitest. Extensión: Chrome MV3 + esbuild.
- `make check` debe quedar verde antes de cada commit.

## Fuentes de datos (límites que no se negocian)

- Cartas: FUT.GG (`/api/fut/players/v2/27/`). Precios PC: EasySBC (`api-fc27.easysbc.io/players`, cabecera `Platform: PC`). Club y mercado visto: extensión propia sobre la web app de EA.
- Máximo 1 petición/s por fuente, caché, parar ante 403/429, **nunca** saltarse protecciones anti-bots (FUTBIN y la ruta de precios de FUT.GG quedan fuera).
- La extensión **solo lee** lo que la web app de EA ya recibe; nunca hace peticiones a EA ni toca el mercado.

## Estado (2026-11-17)

- Plan 1 (cimientos + motor solver): en `main`.
- Plan 2 (Datos fase 1): terminado y revisado en `feat/datos-fase-1`. Falta la prueba manual con el club real (cargar la extensión con "modo muestras", navegar Club, Almacén SBC, Lista de transferencias y una búsqueda manual), revisar `apps/api/var/samples/`, ajustar `apps/extension/src/parse.ts` y los fixtures si el formato real de EA difiere, y luego integrar en `main`.
- Siguiente: Plan 3 (retos SBC desde la extensión/EasySBC, pantalla de reto, solver sobre el club real).
