# Meta Rating (módulo de cálculo) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un módulo puro que puntúe una carta en un rol (meta rating 0–99.9) a partir
de sus atributos, con tabla rol→pesos propia y tiers por percentil.

**Architecture:** Módulo `fcsl_api.meta` sin BD (espejo de `solver/chemistry.py`):
un modelo de atributos de carta, una tabla de roles (atributos clave + pesos +
PlayStyles+ relevantes + AcceleRATE preferido) sembrada desde la metodología pública
de EasySBC, y una función `meta_rating(attrs, role)`. Los pesos son nuestros y se
afinan luego por calibración; los tests fijan la mecánica, no los números de EasySBC.

**Tech Stack:** Python 3.13, Pydantic v2, pytest. Sin OR-Tools ni red en este módulo.

**Spec:** `docs/superpowers/specs/2026-11-18-meta-rating-squad-builder-design.md`

## Global Constraints

- Responder/commits en español; commits **sin** `Co-Authored-By`.
- `make check` (ruff + pytest) verde antes de cada commit.
- Módulo **puro**: sin acceso a BD ni red; entradas por fixtures en los tests.
- Escala del meta rating: **0–99.9**. Tiers: `S, A+, A, B+, B` por percentil.
- Pesos por rol **versionados en el repo** y marcados como ajustables (semilla).

## Review Focus

- **Carta sin algún atributo** (dato incompleto de EA): `meta_rating` no debe
  romper; atributo ausente cuenta como 0 y se registra. (Test en Task 3.)
- **Rol desconocido** para una carta: pedir el meta de un rol que la carta no juega
  debe dar un error claro o un score degradado definido, no una excepción opaca.
  (Test en Task 2.)
- **Pesos de un rol que no suman 1**: la normalización debe seguir dando 0–99.9
  (se normaliza por la suma real de pesos, no se asume 1). (Test en Task 3.)
- **AcceleRATE None** (altura/stats que no determinan tipo): el ajuste de AcceleRATE
  es 0, no penaliza. (Test en Task 3.)
- **Tiers con empates / pocos jugadores**: los cortes por percentil no deben fallar
  con 1–2 cartas ni dejar huecos de tier. (Test en Task 4.)

---

### Task 1: Modelo de atributos de carta

**Files:**
- Create: `apps/api/src/fcsl_api/meta/__init__.py`
- Create: `apps/api/src/fcsl_api/meta/attributes.py`
- Test: `apps/api/tests/test_meta_attributes.py`

**Interfaces:**
- Produces: `PlayerAttributes` (Pydantic v2) con los stats in-game como enteros
  (`acceleration, sprint_speed, positioning, finishing, shot_power, long_shots,
  volleys, penalties, vision, crossing, fk_accuracy, short_passing, long_passing,
  curve, agility, balance, reactions, ball_control, dribbling, composure,
  interceptions, heading, def_awareness, standing_tackle, sliding_tackle, jumping,
  stamina, strength, aggression`), más `skill_moves:int`, `weak_foot:int`,
  `accelerate: Literal["EXPLOSIVE","CONTROLLED","LENGTHY"] | None`,
  `play_styles: list[int]`, `play_styles_plus: list[int]`. Método
  `get(stat: str) -> int` que devuelve 0 si el stat no está (dato incompleto).

- [ ] **Step 1: Write the failing test** — `test_player_attributes_defaults_missing_to_zero`:
  construir `PlayerAttributes` con solo unos pocos stats y `attrs.get("agility")`
  devuelve el valor; `attrs.get("vision")` ausente devuelve `0`.
- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/test_meta_attributes.py -v` → FAIL (módulo no existe).
- [ ] **Step 3: Implement `PlayerAttributes` en `meta/attributes.py`** con los campos
  anteriores (stats `int = 0` por defecto) y `get(stat)` que lee el campo o 0.
- [ ] **Step 4: Run test to verify it passes** — misma orden → PASS.
- [ ] **Step 5: Commit** — `git add apps/api/src/fcsl_api/meta/ apps/api/tests/test_meta_attributes.py && git commit -m "meta: modelo de atributos de carta"`

### Task 2: Tabla de roles (atributos clave + pesos, semilla)

**Files:**
- Create: `apps/api/src/fcsl_api/meta/roles.py`
- Test: `apps/api/tests/test_meta_roles.py`

**Interfaces:**
- Consumes: nada.
- Produces: `RoleWeights` (dataclass: `key_stats: dict[str, float]`,
  `playstyles_plus: list[int]`, `best_accelerate: str | None`),
  `ROLES: dict[str, RoleWeights]` con una semilla de roles por posición
  (al menos: `adv_forward` ST, `falseback` LB/RB, `box_crasher` CDM, un rol de CB y
  uno de CM), y `role_for(position: str) -> str` que da el rol por defecto de una
  posición. `get_role(role: str) -> RoleWeights` lanza `KeyError` claro si no existe.

- [ ] **Step 1: Write the failing test** — `test_roles_seed_and_lookup`: `ROLES`
  contiene `adv_forward`; `ROLES["adv_forward"].key_stats` incluye `acceleration`,
  `finishing`, `agility` con pesos > 0; `role_for("ST")` devuelve un rol existente;
  `get_role("no_existe")` lanza `KeyError`.
- [ ] **Step 2: Run test to verify it fails** — `uv run pytest tests/test_meta_roles.py -v` → FAIL.
- [ ] **Step 3: Implement `roles.py`** con la semilla (pesos justificados desde los
  "top stats por rol" públicos de EasySBC; comentar que son ajustables) y los lookups.
- [ ] **Step 4: Run test to verify it passes** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "meta: tabla de roles y pesos (semilla)"`

### Task 3: Cálculo del meta rating

**Files:**
- Create: `apps/api/src/fcsl_api/meta/rating.py`
- Test: `apps/api/tests/test_meta_rating.py`

**Interfaces:**
- Consumes: `PlayerAttributes` (Task 1), `ROLES`/`get_role` (Task 2).
- Produces: `meta_rating(attrs: PlayerAttributes, role: str) -> float` en `[0, 99.9]`.
  Fórmula: media ponderada de `attrs.get(stat)` por `key_stats` (normalizada por la
  suma de pesos) → base 0–99; + bonus por cada `play_styles_plus` que esté en el rol;
  + ajuste si `accelerate == best_accelerate`; + aporte menor de `skill_moves`/
  `weak_foot`; recortado a `[0, 99.9]`.

- [ ] **Step 1: Write the failing tests** en `test_meta_rating.py`:
  - `test_higher_key_stats_score_higher`: dos cartas iguales salvo `finishing`/
    `acceleration` altos vs bajos en `adv_forward` → la rápida-definidora puntúa más.
  - `test_playstyle_plus_raises_score`: añadir un PlayStyle+ relevante al rol sube el
    score frente a la misma carta sin él.
  - `test_missing_stat_counts_zero_no_crash`: carta sin algunos stats no rompe y
    puntúa menos que la completa.
  - `test_bounds_and_weights_not_summing_one`: con pesos de rol que no suman 1 el
    score sigue en `[0, 99.9]`.
  - `test_accelerate_none_no_penalty`: `accelerate=None` no baja el score respecto a
    un AcceleRATE no preferido.
- [ ] **Step 2: Run tests to verify they fail** — `uv run pytest tests/test_meta_rating.py -v` → FAIL.
- [ ] **Step 3: Implement `meta_rating` en `rating.py`** según la fórmula de arriba.
- [ ] **Step 4: Run tests to verify they pass** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "meta: cálculo del meta rating por carta y rol"`

### Task 4: Tiers por percentil

**Files:**
- Modify: `apps/api/src/fcsl_api/meta/rating.py`
- Test: `apps/api/tests/test_meta_tiers.py`

**Interfaces:**
- Consumes: scores de meta rating (floats).
- Produces: `tier_for(score: float, population: list[float]) -> str` que devuelve uno
  de `S, A+, A, B+, B` según el percentil del score en `population` (cortes:
  S ≥ p95, A+ ≥ p85, A ≥ p65, B+ ≥ p40, B el resto; los cortes son constantes
  nombradas y ajustables).

- [ ] **Step 1: Write the failing tests** — `test_tiers_by_percentile`: en una
  población conocida, el máximo cae en `S` y el mínimo en `B`; `test_tiers_tiny_population`:
  con 1–2 cartas no lanza y devuelve un tier válido.
- [ ] **Step 2: Run tests to verify they fail** → FAIL.
- [ ] **Step 3: Implement `tier_for`** y las constantes de corte en `rating.py`.
- [ ] **Step 4: Run tests to verify they pass** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "meta: tiers por percentil"`
