# Cimientos + motor del solver — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar el monorepo funcionando (API, base de datos, web vacía) y un motor de SBC exacto en CP-SAT, probado contra fuerza bruta y expuesto por HTTP.

**Architecture:** API FastAPI en Python con el solver como paquete interno puro (`fcsl_api.solver`): funciones puras de media y química, un constructor de modelo CP-SAT y un servicio que poda el pool, valora cartas y resuelve. Postgres con Alembic solo con el esquema inicial (se llena en el plan de Datos). Web Next.js con navegación y estado del API.

**Tech Stack:** Python 3.13 + uv, FastAPI, Pydantic v2, OR-Tools (CP-SAT), SQLAlchemy 2 + Alembic + psycopg 3, pytest; Postgres 16 en Docker Compose; Next.js (App Router) + TypeScript + Tailwind + Vitest/Testing Library; Node 24 + npm.

**Spec:** `docs/superpowers/specs/2026-11-16-fc-squad-lab-design.md` (cubre Fase 0 y el modelo de optimización de Fase 2 §7.2). Fuera de este plan y en planes siguientes: Fase 1 (fuente de cartas/precios, extensión, Mi club), resto de Fase 2 (carga de retos, pantalla de reto, alternativas por hueco, conjuntos repetibles), Fases 3–5.

## Global Constraints

- Solo uso personal; nada se despliega fuera del Mac en este plan.
- Precios de **PC**. Ninguna pieza del sistema actúa sobre el mercado de EA.
- Python **3.13** (la spec decía 3.12; en el Mac hay 3.13.7 y uv). Gestor: `uv`. Paquete: `fcsl_api` en `apps/api/src/fcsl_api`.
- Puertos: API **8787**, web **3030**, Postgres **5544** (host) → 5432 (contenedor).
- Identificadores en inglés; textos de UI en español.
- Valoración por defecto (spec §7.2): intransferible propia = 0; transferible propia = **95 %** de su precio; duplicados y almacén SBC con descuento extra configurable (por defecto **10 %**); mercado = precio PC; cartas de mercado sin precio no entran.
- Límite de tiempo por resolución por defecto **10 s**; la respuesta dice si es óptima.
- Química y media: constantes aisladas en un solo módulo, marcadas "validar contra el juego".
- Git local en `~/Code/Personal/fc-squad-lab`, identidad personal (`camiloabrilth1999@gmail.com`), commits sin trailer de co-autor (preferencia de Camilo). Sin remoto en este plan.

## Review Focus

1. **SBC imposible con el pool dado** → estado `infeasible` con un `message` legible (p. ej. "Ningún jugador puede ocupar la posición ST"), nunca excepción 500 ni espera hasta el timeout. → Task 6 y Task 11.
2. **Dos versiones del mismo jugador** (mismo `asset_id`, p. ej. oro y TOTW) → nunca aparecen juntas en una solución. → Task 6.
3. **Timeout con solución parcial** → devuelve la mejor encontrada con `status="feasible"`; sin ninguna → `status="unknown"`. → Task 10.
4. **Pool grande (miles de cartas de mercado)** → la poda lo reduce y un SBC de 11 jugadores con media + química resuelve en < 10 s. → Task 10.
5. **Carta propia transferible sin precio conocido** → cuesta 0 pero no rompe; carta de mercado sin precio → excluida. → Task 10.

---

## Estructura de archivos

```
fc-squad-lab/
  .gitignore  README.md  docker-compose.yml  Makefile
  apps/api/
    pyproject.toml  alembic.ini  Dockerfile
    alembic/env.py  alembic/versions/0001_initial.py
    src/fcsl_api/
      main.py            # FastAPI app, /health, monta routers
      settings.py        # Settings (pydantic-settings): DATABASE_URL
      db.py              # engine/session
      models_db.py       # tablas SQLAlchemy: cards, prices, club_items
      routes/solve.py    # POST /solve, POST /solve/pools
      solver/
        models.py        # Card, Requirement, SolveRequest, Solution...
        rating.py        # team_rating (pura)
        chemistry.py     # constantes + player_chemistry (pura)
        cpsat.py         # build_model / extract (CP-SAT)
        requirements.py  # aplica cada Requirement al modelo
        pool.py          # build_pool (filtro + poda)
        valuation.py     # card_cost, objective weights
        service.py       # solve, solve_all_pools
    tests/
      conftest.py  fixtures.py  bruteforce.py
      test_health.py test_db.py test_rating.py test_chemistry.py
      test_cpsat_basic.py test_rating_constraint.py test_chem_constraint.py
      test_requirements.py test_pool_valuation.py test_service.py test_api_solve.py
  apps/web/            # create-next-app
    src/components/Nav.tsx  src/components/ApiStatus.tsx
    src/app/{mi-club,sbc,plantillas,evoluciones,objetivos}/page.tsx
    src/components/__tests__/Nav.test.tsx  ApiStatus.test.tsx
```

---

### Task 1: Repo + API mínima

**Files:** Create `.gitignore`, `README.md`, `Makefile`, `apps/api/pyproject.toml`, `apps/api/src/fcsl_api/__init__.py`, `apps/api/src/fcsl_api/main.py`, `apps/api/tests/test_health.py`

**Interfaces:**
- Produces: `fcsl_api.main.app: FastAPI`; `GET /health -> {"status": "ok", "db": "ok" | "down" | "unchecked"}` (en esta tarea siempre `"unchecked"`).

- [ ] **Step 1:** `git init` en `~/Code/Personal/fc-squad-lab` (la carpeta ya tiene `docs/`). `.gitignore` con `.venv/`, `__pycache__/`, `node_modules/`, `.next/`, `.env`.
- [ ] **Step 2:** `cd apps/api && uv init --package --name fcsl-api --python 3.13` y `uv add fastapi uvicorn[standard] pydantic pydantic-settings ortools sqlalchemy alembic "psycopg[binary]"`; `uv add --dev pytest httpx ruff`.
- [ ] **Step 3: Test que falla** `tests/test_health.py::test_health_ok`: `TestClient(app).get("/health")` → 200 y `json()["status"] == "ok"`.
- [ ] **Step 4:** `uv run pytest tests/test_health.py -v` → FAIL (no existe `app`).
- [ ] **Step 5:** Implementar `main.py` con `app = FastAPI(title="FC Squad Lab API")` y `/health`.
- [ ] **Step 6:** `uv run pytest -v` → PASS; `uv run ruff check .` → sin errores.
- [ ] **Step 7:** `Makefile` con `api-test` (`cd apps/api && uv run pytest`), `api-dev` (`uvicorn fcsl_api.main:app --port 8787 --reload`). Commit `chore: monorepo y API mínima`.

### Task 2: Postgres, esquema inicial y salud de la DB

**Files:** Create `docker-compose.yml`, `apps/api/Dockerfile`, `src/fcsl_api/settings.py`, `db.py`, `models_db.py`, `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_initial.py`, `tests/test_db.py`; Modify `main.py`.

**Interfaces:**
- Produces: `Settings.database_url: str` (env `DATABASE_URL`, por defecto `postgresql+psycopg://fcsl:fcsl@localhost:5544/fcsl`); `db.get_engine() -> Engine`; `db.ping() -> bool`.
- Tablas (Alembic `0001_initial`):
  - `cards(resource_id INT PK, asset_id INT NOT NULL, name TEXT, rating SMALLINT, positions TEXT[], league_id INT, nation_id INT, club_id INT, rare BOOL, rarity_tags TEXT[], is_icon BOOL, is_hero BOOL, updated_at TIMESTAMPTZ)`; índice en `asset_id`.
  - `prices(resource_id INT, platform TEXT, price INT, captured_at TIMESTAMPTZ, source TEXT, PK(resource_id, platform))`.
  - `club_items(item_id BIGINT PK, resource_id INT, untradeable BOOL, location TEXT, duplicate BOOL, loan BOOL, last_sale_price INT NULL, imported_at TIMESTAMPTZ)`.
- `/health` pasa a devolver `db: "ok" | "down"` según `db.ping()`.

- [ ] **Step 1:** `docker-compose.yml` con servicio `db` (`postgres:16`, usuario/clave/DB `fcsl`, puerto `5544:5432`, volumen nombrado) y `api` (build `apps/api`, puerto `8787`, `DATABASE_URL` hacia `db:5432`). Si `docker info` falla, pedir a Camilo que abra Docker Desktop.
- [ ] **Step 2: Tests que fallan** en `tests/test_db.py` (marcador `@pytest.mark.db`, saltan si `db.ping()` es False): `test_migration_creates_tables` (tras `alembic upgrade head`, existen `cards`, `prices`, `club_items`); `test_health_reports_db_ok` (`/health` → `db == "ok"`). En `test_health.py` añadir `test_health_reports_db_down` con `DATABASE_URL` a un puerto cerrado → `db == "down"` y status 200.
- [ ] **Step 3:** `docker compose up -d db` y `uv run pytest -v` → FAIL.
- [ ] **Step 4:** Implementar settings, db, modelos y migración; `alembic upgrade head` contra la DB.
- [ ] **Step 5:** `uv run pytest -v` → PASS (los 3). `docker compose up -d --build api` y `curl localhost:8787/health` → `{"status":"ok","db":"ok"}`.
- [ ] **Step 6:** Commit `feat: postgres y esquema inicial`.

### Task 3: Web con navegación y estado del API

**Files:** Create `apps/web` (create-next-app), `src/components/Nav.tsx`, `src/components/ApiStatus.tsx`, 5 páginas, 2 tests; Modify `src/app/layout.tsx`, `src/app/page.tsx`; añadir `cors` en `main.py` para `http://localhost:3030`.

**Interfaces:**
- Consumes: `GET /health` (Task 2).
- Produces: `NAV_ITEMS: {href: string; label: string}[]` exportado de `Nav.tsx` = `[{"/mi-club","Mi club"},{"/sbc","SBC"},{"/plantillas","Plantillas"},{"/evoluciones","Evoluciones"},{"/objetivos","Objetivos"}]`; `ApiStatus({ apiUrl }: { apiUrl: string })`.

- [ ] **Step 1:** `npx create-next-app@latest apps/web --ts --tailwind --eslint --app --src-dir --use-npm --no-import-alias --turbopack`; anotar la versión instalada en `README.md`. Script `dev` en puerto 3030. Instalar `vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom`.
- [ ] **Step 2: Tests que fallan:** `Nav.test.tsx::renders all sections` (5 enlaces con esos textos y hrefs); `ApiStatus.test.tsx::shows connected` (fetch mock `{status:"ok",db:"ok"}` → texto "API conectada"), `::shows db down` (`db:"down"` → "Base de datos caída"), `::shows offline` (fetch rechaza → "API sin conexión").
- [ ] **Step 3:** `npm test` → FAIL.
- [ ] **Step 4:** Implementar `Nav`, `ApiStatus` (cliente, `apiUrl` desde `NEXT_PUBLIC_API_URL`, por defecto `http://localhost:8787`), layout con `Nav`, home con `ApiStatus`, 5 páginas con su título y "Próximamente".
- [ ] **Step 5:** `npm test` → PASS; `npm run build` → OK; con API arriba, `npm run dev` y abrir `localhost:3030` → "API conectada".
- [ ] **Step 6:** Commit `feat: web con navegación y estado del API`.

### Task 4: Modelos del solver y media de equipo

**Files:** Create `solver/__init__.py`, `solver/models.py`, `solver/rating.py`, `tests/fixtures.py`, `tests/test_rating.py`

**Interfaces (Produces, Pydantic v2):**
```python
Position = str  # "GK","LB","CB","RB","LWB","RWB","CDM","CM","CAM","LM","RM","LW","RW","CF","ST"
class Card(BaseModel):
    card_id: str                     # "club:<item_id>" | "market:<resource_id>"
    resource_id: int; asset_id: int; name: str
    rating: int                      # 40..99
    positions: list[Position]        # preferida primero, no vacía
    league_id: int; nation_id: int; club_id: int
    rare: bool = False
    rarity_tags: list[str] = []      # p. ej. "TOTW", "SPECIAL"
    is_icon: bool = False; is_hero: bool = False
    source: Literal["club", "market"]
    untradeable: bool = False; duplicate: bool = False; in_sbc_storage: bool = False
    price: int | None = None         # PC
    @property level -> Literal["bronze","silver","gold"]   # <65 bronze, 65–74 silver, >=75 gold
class RequirementKind(StrEnum):
    TEAM_RATING, TEAM_CHEMISTRY, PLAYER_CHEMISTRY, PLAYER_RATING,
    LEAGUE_PLAYERS, NATION_PLAYERS, CLUB_PLAYERS,
    DISTINCT_LEAGUES, DISTINCT_NATIONS, DISTINCT_CLUBS,
    SAME_LEAGUE, SAME_NATION, SAME_CLUB,
    LEVEL_PLAYERS, RARE_PLAYERS, TAG_PLAYERS
class Requirement(BaseModel):
    kind: RequirementKind; op: Literal["min","max","exact"] = "min"; value: int
    ids: list[int] = []   # *_PLAYERS: ids aceptados
    tags: list[str] = []  # LEVEL_PLAYERS: ["gold"]; TAG_PLAYERS: ["TOTW"]
class Objective(StrEnum): CHEAPEST = "cheapest"; USE_CLUB = "use_club"; FEWEST_BUYS = "fewest_buys"
class ValuationSettings(BaseModel):
    tradeable_factor: float = 0.95; duplicate_discount: float = 0.10; storage_discount: float = 0.10
class SolveRequest(BaseModel):
    slots: list[Position]            # 1..11
    requirements: list[Requirement] = []
    cards: list[Card]
    pool: Literal["club","both","market"] = "both"
    objective: Objective = Objective.CHEAPEST
    valuation: ValuationSettings = ValuationSettings()
    include_card_ids: list[str] = []; exclude_card_ids: list[str] = []
    time_limit_s: float = 10.0
class Assignment(BaseModel): slot_index: int; position: Position; card_id: str
class Solution(BaseModel):
    status: Literal["optimal","feasible","infeasible","unknown"]
    pool: Literal["club","both","market"]
    assignments: list[Assignment] = []
    cost: int = 0; team_rating: int = 0; team_chemistry: int = 0
    player_chemistry: dict[str, int] = {}
    solve_time_s: float = 0.0; message: str | None = None
```
- `rating.team_rating(ratings: Sequence[int]) -> int`: n = len, S = suma, exceso = Σ max(0, r − S/n), valor = (S + exceso)/n, devuelve `floor(valor)` (constante `ROUNDING = "floor"`, validar contra el juego). Lista vacía → 0.
- `tests/fixtures.py::make_card(**overrides) -> Card` con valores por defecto válidos (rating 75, positions ["CM"], liga/nación/club 1, source "market", price 1000).

- [ ] **Step 1: Tests que fallan** (`test_rating.py`): `test_all_equal` (11×84 → 84); `test_excess_lifts` (10×83 + 1×90 → 84; cálculo: S=920, exceso≈6.36, valor≈84.21); `test_floor` (11×83 con uno de 84 → 83); `test_small_squad` ([80, 90, 70] → **83**: S=240, media 80, exceso=10, 250/3=83.3); `test_empty` → 0; `test_card_level` (64 bronze, 65 silver, 74 silver, 75 gold); `test_card_requires_positions` (positions [] → ValidationError).
- [ ] **Step 2:** `uv run pytest tests/test_rating.py -v` → FAIL.
- [ ] **Step 3:** Implementar `models.py` y `rating.py`.
- [ ] **Step 4:** → PASS. Commit `feat(solver): modelos y media de equipo`.

### Task 5: Química (función pura)

**Files:** Create `solver/chemistry.py`, `tests/test_chemistry.py`

**Interfaces:**
- Produces: constantes (validar contra el juego) `CLUB_THRESHOLDS = (2, 5, 7)`, `LEAGUE_THRESHOLDS = (3, 5, 8)`, `NATION_THRESHOLDS = (2, 5, 8)`, `MAX_PLAYER_CHEM = 3`, `ICON_NATION_WEIGHT = 2`, `HERO_LEAGUE_WEIGHT = 2`.
- `points(count: int, thresholds: tuple[int,int,int]) -> int` (0..3: nº de umbrales alcanzados).
- `group_counts(cards: Sequence[Card]) -> tuple[Counter[int], Counter[int], Counter[int]]` (club, liga, nación). Cada carta suma 1 a su club, liga y nación; icono suma `ICON_NATION_WEIGHT` a su nación; héroe suma `HERO_LEAGUE_WEIGHT` a su liga.
- `player_chemistry(cards: Sequence[Card]) -> dict[str, int]`: icono/héroe → 3; resto → min(3, points(club)+points(liga)+points(nación)). Todas las cartas recibidas se asumen en posición (el solver solo coloca cartas en posiciones que pueden jugar).
- `team_chemistry(cards) -> int` = suma de `player_chemistry`.

- [ ] **Step 1: Tests que fallan:** `test_points` (club: 1→0, 2→1, 5→2, 7→3; liga: 2→0, 3→1, 8→3); `test_single_player_zero`; `test_two_same_club_and_nation` (2 cartas mismo club y nación, distinta liga → 2 cada una); `test_full_league` (11 de la misma liga, clubes y naciones distintos → 3 cada una, total 33); `test_icon_always_three` y `test_icon_doubles_nation` (icono + 1 compatriota → el compatriota tiene nación=1 punto); `test_hero_doubles_league` (héroe + 1 de su liga → el otro tiene liga 3 → 1 punto); `test_cap_three`.
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): química pura`.

### Task 6: Modelo CP-SAT base (huecos, elegibilidad, jugador único, coste)

**Files:** Create `solver/cpsat.py`, `tests/bruteforce.py`, `tests/test_cpsat_basic.py`

**Interfaces:**
- Consumes: `Card`, `Position`, `Solution` (Task 4).
- Produces:
```python
@dataclass
class SbcModel:
    model: cp_model.CpModel
    cards: list[Card]
    slots: list[Position]
    x: dict[tuple[int, int], cp_model.IntVar]    # (card_idx, slot_idx) booleana; solo si slot ∈ card.positions
    used: list[cp_model.IntVar]                   # used[c] = Σ_s x[c,s]
    sum_rating: cp_model.IntVar                   # Σ rating·used
def build_base_model(cards: list[Card], slots: list[Position], costs: list[int]) -> SbcModel
def solve_model(m: SbcModel, objective_terms: list[tuple[int, IntVar]], time_limit_s: float) -> tuple[str, list[Assignment], float]
def eligibility_problem(cards, slots) -> str | None   # "Ningún jugador puede ocupar la posición ST" o None
```
- Restricciones: cada hueco exactamente una carta; cada carta como mucho un hueco; Σ used sobre cartas del mismo `asset_id` ≤ 1. Objetivo base: minimizar Σ costs[c]·used[c] (los términos llegan por `objective_terms`). `solve_model` devuelve (`"optimal"|"feasible"|"infeasible"|"unknown"`, asignaciones, segundos), usando `num_workers=8`.
- `tests/bruteforce.py::brute_force(cards, slots, costs, check: Callable[[list[Card]], bool]) -> int | None`: recorre todas las asignaciones válidas (sin repetir `asset_id`) y devuelve el coste mínimo que cumple `check`. Solo para pools ≤ 8 cartas y ≤ 4 huecos.

- [ ] **Step 1: Tests que fallan:** `test_fills_every_slot`; `test_respects_positions` (GK solo lo ocupa una carta con "GK"); `test_picks_cheapest`; `test_never_same_asset` (dos versiones del mismo `asset_id` muy baratas + una cara distinta, 2 huecos → usa una sola versión); `test_infeasible_when_no_eligible` (`eligibility_problem` → mensaje con "ST"; `solve_model` → `"infeasible"`); `test_matches_bruteforce` (5 pools aleatorios con semilla fija, 6–8 cartas, 3 huecos: coste CP-SAT == brute_force).
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): modelo CP-SAT base`.

### Task 7: Restricción de media de equipo

**Files:** Modify `solver/cpsat.py`; Create `solver/requirements.py`, `tests/test_rating_constraint.py`

**Interfaces:**
- Produces: `apply_requirement(m: SbcModel, req: Requirement) -> None` en `requirements.py` (despacha por `req.kind`; esta tarea implementa `TEAM_RATING` y `PLAYER_RATING`; otras kinds lanzan `NotImplementedError` hasta su tarea).
- `TEAM_RATING` (op min/exact): con n = nº huecos, para cada carta `e_c = max(0, n·rating_c·used_c − sum_rating)` (`AddMaxEquality`; con used_c = 0 la expresión es ≤ 0); exige `n·sum_rating + Σ e_c ≥ n²·value` (min) — equivale a `team_rating ≥ value` con `floor`. `exact`: además `< n²·(value+1)`.
- `PLAYER_RATING`: op min/max/exact sobre cada carta usada (`used_c → rating op value`; como rating es constante, basta con fijar `used_c = 0` para las que no cumplen).

- [ ] **Step 1: Tests que fallan:** `test_team_rating_min` (solución → `rating.team_rating` de las cartas elegidas ≥ objetivo); `test_team_rating_uses_excess` (caso donde la media simple no llega pero el exceso sí: el solver la encuentra y es más barata que subir a todos); `test_team_rating_exact`; `test_player_rating_bounds`; `test_rating_matches_bruteforce` (5 pools semilla fija con `check = team_rating ≥ T`).
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): media de equipo`.

### Task 8: Restricciones de química

**Files:** Modify `solver/requirements.py`, `solver/cpsat.py`; Create `tests/test_chem_constraint.py`

**Interfaces:**
- Consumes: constantes de `chemistry.py` (Task 5).
- Produces: `add_chemistry(m: SbcModel) -> dict[int, IntVar]` (química 0..3 por carta, 0 si no se usa; se crea una sola vez y se cachea en `m`); `TEAM_CHEMISTRY` (Σ química op value) y `PLAYER_CHEMISTRY` (cada carta usada ≥ value; `min` es el único op válido).
- Modelado: para cada club/liga/nación presente en el pool, `count_k = Σ peso·used`; booleanas `reach_k_t ⇔ count_k ≥ umbral_t`; puntos = Σ reach; química de carta normal = min(3, pc+pl+pn) con `AddMinEquality` y forzada a 0 si `used=0`; icono/héroe = 3·used.

- [ ] **Step 1: Tests que fallan:** `test_team_chem_min` (la química recalculada con `chemistry.team_chemistry` ≥ objetivo); `test_player_chem_min`; `test_icon_counts_double` (pool donde solo cumple usando el icono); `test_model_chem_equals_pure` (para cada solución en 5 pools aleatorios, la química del modelo == `player_chemistry` pura); `test_chem_matches_bruteforce`.
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): química en el modelo`.

### Task 9: Requisitos de liga/nación/club, distintos, iguales, nivel, rareza y etiquetas

**Files:** Modify `solver/requirements.py`; Create `tests/test_requirements.py`

**Interfaces (semántica exacta):**
- `LEAGUE_PLAYERS | NATION_PLAYERS | CLUB_PLAYERS`: nº de cartas usadas cuyo id ∈ `ids`, op value.
- `DISTINCT_LEAGUES | DISTINCT_NATIONS | DISTINCT_CLUBS`: nº de grupos con al menos una carta usada, op value.
- `SAME_LEAGUE | SAME_NATION | SAME_CLUB`: `min` → existe un grupo con ≥ value cartas; `max` → ningún grupo supera value; `exact` → el grupo mayor tiene exactamente value.
- `LEVEL_PLAYERS` (`tags` ⊆ {"bronze","silver","gold"}), `RARE_PLAYERS` (rare=True), `TAG_PLAYERS` (algún tag de `tags` ∈ `rarity_tags`): nº de cartas usadas que cumplen, op value.
- Iconos y héroes cuentan por sus propios ids de liga/club/nación para estos requisitos (sin pesos dobles; los pesos son solo de química).

- [ ] **Step 1: Tests que fallan:** uno por kind y op (al menos min y max de cada familia, exact en `SAME_*` y `*_PLAYERS`), cada uno verificando la solución con una función de comprobación en Python sobre las cartas elegidas; `test_combined_realistic` (11 huecos 4-4-2, media 84, química 25, mín 1 TOTW, máx 5 de la misma liga, pool sintético de 80 cartas → status optimal y todas las comprobaciones pasan).
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): requisitos de grupos, nivel y rareza`.

### Task 10: Pool, poda, valoración y objetivos

**Files:** Create `solver/pool.py`, `solver/valuation.py`, `tests/test_pool_valuation.py`

**Interfaces:**
- `valuation.card_cost(card: Card, v: ValuationSettings) -> int`: mercado → `price`; propia intransferible → 0; propia transferible → `round((price or 0) * v.tradeable_factor)`; si `duplicate` o `in_sbc_storage` → multiplicar por `(1 − descuento)` (el mayor de los que apliquen).
- `valuation.objective_terms(m: SbcModel, costs: list[int], objective: Objective) -> list[tuple[int, IntVar]]`, lexicográfico con multiplicador `BIG = 10**6`:
  - `CHEAPEST`: `100·coste − bonus` por carta (bonus 1 si propia intransferible, +1 si duplicada o en almacén).
  - `FEWEST_BUYS`: `BIG·[source=="market"] + coste`.
  - `USE_CLUB`: `−BIG·[propia intransferible o duplicada] + coste`.
- `pool.build_pool(cards, pool, slots, requirements, include_ids, exclude_ids) -> list[Card]`:
  1. por `pool`: `club` → source club; `market` → source market; `both` → ambas;
  2. quita `exclude_ids`, cartas de mercado sin precio y las que no juegan en ningún hueco;
  3. quita las que violan `PLAYER_RATING`;
  4. poda de mercado: agrupa por (rating, liga, nación, club, posiciones∩huecos, rare, rarity_tags, is_icon, is_hero) y conserva las **2** más baratas por grupo; nunca poda cartas propias ni `include_ids`.
- `include_card_ids` se fuerza en el modelo con `used = 1` (la incorporación al modelo la hace el servicio en Task 11).

- [ ] **Step 1: Tests que fallan:** `test_cost_rules` (cada rama de `card_cost`, incluida transferible sin precio → 0); `test_market_without_price_excluded`; `test_pool_filters_by_source`; `test_pruning_keeps_two_cheapest`; `test_pruning_never_drops_club_or_included`; `test_objective_fewest_buys_prefers_club` (con club algo más caro, `FEWEST_BUYS` usa club y `CHEAPEST` mercado); `test_large_pool_under_10s` (11 huecos, 5 000 cartas de mercado sintéticas con semilla fija + media 84 + química 25 → status optimal o feasible y < 10 s); `test_timeout_returns_feasible_or_unknown` (`time_limit_s=0.05` en ese mismo problema → status ∈ {"feasible","unknown"}, sin excepción).
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** → PASS. Commit `feat(solver): pool, poda y valoración`.

### Task 11: Servicio y endpoints HTTP

**Files:** Create `solver/service.py`, `routes/solve.py`, `tests/test_service.py`, `tests/test_api_solve.py`; Modify `main.py`.

**Interfaces:**
- `service.solve(req: SolveRequest) -> Solution`: `build_pool` → `eligibility_problem` (si hay problema → `Solution(status="infeasible", message=...)` sin llamar a CP-SAT) → `build_base_model` → `apply_requirement` por cada requisito → forzar `include_card_ids` → `solve_model` → recalcula `team_rating`, `team_chemistry`, `player_chemistry` con las funciones puras y `cost` = Σ `card_cost`. Si `include_card_ids` no está en el pool → infeasible con mensaje "Jugador incluido no disponible: <id>".
- `service.solve_all_pools(req: SolveRequest) -> list[Solution]`: resuelve `club`, `both`, `market` en ese orden; omite `club` y `both` si no hay cartas propias.
- `POST /solve` (body `SolveRequest`) → `Solution`; `POST /solve/pools` → `list[Solution]`. Body inválido → 422; requisito con op no válido (p. ej. `PLAYER_CHEMISTRY` con `max`) → 422 con mensaje.

- [ ] **Step 1: Tests que fallan:** `test_service_infeasible_message` (huecos con "GK" sin porteros → infeasible y "GK" en message); `test_service_include_missing`; `test_service_metrics_consistent` (rating y química devueltos == funciones puras sobre las cartas asignadas); `test_solve_all_pools_order_and_skip`; `test_api_solve_ok` (TestClient, problema pequeño → 200 y `status=="optimal"`); `test_api_invalid_body_422`; `test_api_invalid_op_422`.
- [ ] **Step 2:** → FAIL. **Step 3:** Implementar. **Step 4:** `uv run pytest -v` (toda la suite) → PASS; `uv run ruff check .` limpio.
- [ ] **Step 5:** Manual: `make api-dev` y `curl -X POST localhost:8787/solve -H 'content-type: application/json' -d @apps/api/tests/data/example_request.json` (crear ese JSON con un problema de 11 huecos) → solución en < 10 s.
- [ ] **Step 6:** Commit `feat: servicio de solver y endpoints /solve`.

### Task 12: Calidad del solver (añadida durante la ejecución, 2026-11-17)

Motivo: con media + química, el benchmark `tests/test_perf.py` (marcado `slow`) da 10/10 soluciones válidas en ~9 s pero solo 2/10 a ≤ 2 % de la mejor conocida (gaps hasta 31 %), con mucha varianza entre ejecuciones. La relajación lineal de la química es casi nula y el arranque en caliente (`cpsat.py`) ignora liga/nación/química/incluidas.

**Files:** Modify `solver/cpsat.py`, `solver/requirements.py`, `solver/pool.py` según haga falta; posible Create `solver/heuristic.py`; Modify `tests/test_perf.py`.

**Interfaces:** sin cambios públicos: `solve_model`, `apply_requirement`, `build_pool`, `service.solve` mantienen firma y semántica. Todos los tests de exactitud existentes (fuerza bruta, modelo == química pura, poda exacta) siguen en verde.

- [ ] **Step 1:** Medir: correr `uv run pytest -m slow tests/test_perf.py -s` 2 veces y anotar gaps y tiempos; referencia `best_known` con 60 s.
- [ ] **Step 2:** Implementar, en este orden, hasta cumplir el listón: (a) heurística constructiva consciente de química (p. ej. elegir 1–3 grupos liga/nación/club objetivo y rellenar barato) + búsqueda local, usada como pista (`add_hint`) y como solución de respaldo; (b) arranque en caliente que respete todos los requisitos e incluidas, y que no pierda su solución si el solve principal no tiene tiempo; (c) reformulación/cortes de química (cotas por grupo, simetría de cartas idénticas) si (a)+(b) no bastan.
- [ ] **Step 3: Listón (benchmark `slow`):** 10/10 válidas en < 10 s y ≥ 8/10 con coste ≤ 1,02 × best_known (best_known = mejor de 60 s), en 2 ejecuciones seguidas.
- [ ] **Step 4:** Suite completa (por defecto) en verde, `ruff check` limpio. Commit `perf(solver): calidad de soluciones con química`.

---

## Después de este plan

Plan 2 — Datos (Fase 1): adaptador de cartas/precios PC con caché, extensión MV3 de solo lectura (club + SBC), importación y pantalla Mi club. Plan 3 — Resto de Fase 2: retos desde la extensión, pantalla de reto, alternativas por hueco, conjuntos repetibles. Antes del Plan 3, validar `chemistry.py` y `rating.py` contra 3 plantillas reales del juego.
