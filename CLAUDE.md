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
- **Ojo con la copia de la extensión**: en esta máquina Chrome carga la extensión desde una copia en
  Windows (`C:\Users\Camilo\fc-squad-lab-extension`), no desde `apps/extension/dist/` de WSL. Tras
  `npm run build` hay que copiar el `dist` a esa carpeta (`/mnt/c/Users/Camilo/fc-squad-lab-extension`)
  y recargar la extensión en `chrome://extensions`; si no, Chrome sigue con el código viejo y los
  imports nuevos (Evoluciones, Objetivos) no llegan. Se comprueba mirando desde qué ruta la carga
  Chrome (`Secure Preferences`) o comparando hashes de `background.js`.
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
- La extensión **solo lee**. Observa lo que la web app de EA recibe y, desde 2026-11-17 (decisión de Camilo, como EasySBC), al iniciar sesión pide a la propia web app que lea el club y el Almacén SBC con sus servicios internos (`services.Club.search`, `services.Item.searchStorageItems`): ≥ 1 s entre peticiones, tope de páginas, una vez por sesión (enfriamiento de 15 min), parar ante el primer error y desactivable en Opciones. **Nunca** peticiones `fetch` propias a EA, ni mercado, pujas, ventas, movimientos o envíos de SBC.

## Estado y seguimiento

El estado vivo de la app (hecho / en curso / pendiente) está en **`ROADMAP.md`** en
la raíz. Mantenerlo actualizado al cerrar cada avance para no perder el seguimiento.

- Fases 0–1 (cimientos, solver, datos reales de EA, SBC) mezcladas en `main` (PR #1).
- En curso: **meta rating propio** + **Squad Builder (Fase A, solo club)**.
