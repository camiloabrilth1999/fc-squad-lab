# ROADMAP — FC Squad Lab

Seguimiento vivo de la app (replicar EasySBC sobre datos propios). Se actualiza a
medida que avanzamos: **Hecho**, **En curso**, **Pendiente / aparcado**. La idea es
que ninguna decisión ni tarea se pierda. Diseño general en
`docs/superpowers/specs/`; planes de implementación en `docs/superpowers/plans/`.

Última actualización: 2026-11-18.

## Hecho (en `main`)

- **Cimientos + solver** (OR-Tools CP-SAT): huecos, único por carta, coste, química,
  valoración de equipo, requisitos.
- **Datos reales de EA**: catálogo de SBC desde captura en vivo de `services.SBC`
  (solo lectura). 55 retos: construcción (OPEN) + de un clic.
- **Importación de club** (extensión, solo lectura) + precios (`easysbc:market`).
- **Solver — mejoras**:
  - jugadores **fuera de posición** (como EA): la posición solo afecta a la química.
  - modelo en posición hueco a hueco en pools pequeños / por cupos en grandes.
  - **RATING_PLAYERS** (códigos 26/28: "N jugadores con GRL ≥/≤ X").
  - **DCP de un clic**: topes de GRL → TEAM_RATING (mín/máx/banda), liga → LEAGUE_PLAYERS.
- **Web**: "Mi club" y página de SBC conectada al backend.
- 337 tests + ruff en verde; benchmark de rendimiento (lento) pasa.
- PR #1 mezclado en `main` (Fases 0–1).

## En curso

- **Meta rating propio** (fundamento del Squad Builder):
  - propio, con nuestros pesos; **EasySBC solo como guía de calibración** (no
    dependemos de su API en el producto).
  - por **(carta, rol)**; entradas: atributos detallados (~35) + PlayStyles(+) +
    AcceleRATE + WF/SM; tabla rol→atributos sembrada desde los "top stats por rol"
    **públicos** de EasySBC; salida 0–99.9 + tiers (S/A+/A/B+/B) por percentil.
  - **Módulo de cálculo `fcsl_api.meta`: HECHO** (atributos, roles/pesos semilla,
    `meta_rating`, tiers; 14 tests). En `feat/squad-builder`.
  - Fuente de stats confirmada (recon 2026-11-18): los **34 stats detallados** están
    solo en la **ficha de carta de FUT.GG** (`/players/<slug>/27-<eaId>/`, HTML SSR
    parseable), no en EA ni en el listado. Ingesta = detalle por carta del club
    (~179), ≤ 1 req/s, caché. `tier-list/player-tier` de FUT.GG como 2ª referencia.
  - **Ingesta de atributos: HECHO** (parser, tabla `card_attributes`, migración 0003,
    `sync_club_attributes`, `make sync-club-attributes`, `/club` devuelve `meta` y
    `meta_role`); primera descarga real hecha (170 cartas del club).
  - **Calibración: HECHA (2026-11-19)**. Referencia de dev = `metaRating` de EasySBC (ya en
    la caché de precios, `var/cache/easysbc`); muestra de ~490 cartas 78+ con stats de FUT.GG
    (`python -m fcsl_api.meta fetch-sample`). Regresión ridge con coef ≥ 0 por rol
    (`python -m fcsl_api.meta fit` → `meta/fitted_weights.json`, versionado). Sobre 630 cartas:
    Pearson 0,81 → **0,974**, MAE 5,5 → **1,25**, sesgo +4,4 → 0,0; corr. en validación
    cruzada 0,93–0,98 por rol. El producto solo lee el JSON, no consulta EasySBC.
    **Portero propio: HECHO**: stats `gk_*` + altura (el listado de FUT.GG trae `height`;
    migración 0005); la altura explica casi todo el desajuste de las porteras (corr. CV del
    portero 0,66 → 0,94; también mejora los roles de campo). Con 8 roles y 757 cartas:
    Pearson **0,981**, MAE **1,09**.
    Límites: PlayStyles como conteo por rol (mejorable con un coeficiente por PlayStyle); la
    referencia mezcla roles de EasySBC dentro de una posición; el meta usa el rol de la
    posición preferida (no el del hueco).
  - Pendiente: (b) ~~mapear ids de PlayStyle+~~ **HECHO**: ids reales
    (tabla de `fut.gg/playstyles`, listas por rol de `best-by-role`), bonus de PlayStyle+/PlayStyle,
    AcceleRATE y estrellas leídos del listado (migración 0004, `meta/compute.py`); (c) ~~calibrar pesos~~ HECHO (ver arriba); (d) ~~stats de portero propios~~ HECHO; (e) ~~PlayStyles no-plus~~ HECHO (0.5 c/u).
- **Squad Builder — Fase A (solo club): API HECHA** (`POST /squad/build`, `squad/builder.py`,
  en posición, Σ meta + química; óptimo al instante con tu club real) + **página web
  `/plantillas` HECHA** (formación, química mínima, once sobre la cancha). **Fuera de posición: HECHO**
  (modos none / family / any, tope `max_out_of_position`, meta por (carta, posición) con el rol
  del hueco; el jugador fuera de posición pierde su química, como en el juego). Con el peso de
  química por defecto (1,5 de meta por punto) el once de tu club no cambia: jugar fuera de
  posición no compensa perder 3 de química; con `chem_weight` 0 sí aparecen. Falta decidir
  si ese peso es el correcto (calibrar contra `metaRating` con química de EasySBC). Descripción original: "mejor XI de tu club" maximizando
  meta + química (la función "best possible squad" de EasySBC). Reusa el solver;
  objetivo = maximizar Σ meta en vez de minimizar coste.

## Pendiente / aparcado (no perder)

- **Squad Builder — Fase B (mercado + filtros)**: **mercado + presupuesto HECHO** (rama
  `feat/squad-market`): `pool: both` + `budget` en `POST /squad/build`; candidatos de
  mercado = capas de Pareto (rating/precio) por posición (`squad/market.py`); stats
  detallados bajo demanda con `make squad-scan ARGS='--formation 442 --budget 150000'`
  (≤ 1 req/s; los candidatos sin stats se excluyen y se avisa con `pending_stats`); la web
  tiene selector de cartas y presupuesto. Con tu club y 150.000 monedas: meta 926,6 → 945,4,
  rating 84 → 86, gasto 109.050 (resultado *feasible* al límite de 10 s).
  **Filtros y control HECHO** (rama `feat/squad-filters`): `formation: "best"` (prueba las
  16 y elige la de mayor meta + química), `include_card_ids` (fijar), `exclude_card_ids`,
  `league_ids` / `nation_ids` / `club_ids` (también para candidatos del mercado; una carta de
  mercado fijada entra aunque no sea candidata). La web tiene "Mejor formación" y botones
  📌 fijar / 🚫 excluir por jugador (recalcula al instante).
  **Falta**: selector de ligas/naciones/clubes en la web (no tenemos tabla de nombres, solo
  ids), fuente icono/héroe, escaneo desde la web (hoy por CLI) y afinar el rendimiento del
  modelo con mercado (no llega a probar optimalidad en 10 s).
- **Players DB: HECHA (parte 1)** (rama `feat/players-db`): `GET /players` (filtros por nombre,
  posición, rol, media, meta, liga/nación/club, tier, fuente, precio; orden y paginación) y
  `GET /players/{id}` (stats, cara y meta por rol); página web `/jugadores`. El meta de **todas**
  las cartas sale de un modelo por stats de la cara (`meta/face.py`, `fitted_face_weights.json`,
  `python -m fcsl_api.meta fit-face`) calibrado contra EasySBC: corr. en validación 0,92–0,99,
  MAE 1,5 sobre 6.353 cartas (1,2 con stats detallados). Se precalcula en `card_meta`
  (`make meta-materialize`, migraciones 0006 y 0007; hay que re-correrlo tras sync-cards).
  Fuentes: stats detallados si existen, si no cara (`~` en la web). **Falta**: detalle de carta
  en la web, meta por rol alternativo en la lista, filtros por liga/nación/club con nombres,
  y tiers/ranking por rol en la vista.
- **Squad Recommendations** del club (se cubre con Squad Builder Fase A).
- **Gallery**: modo soluciones de sets de galería sobre el solver de SBC.
- **Evolutions**: capturar datos de evoluciones de EA + planificación.
- **Objectives**: seguimiento de objetivos/hitos.
- **Vistas de valor**: "hidden profit" / "SBC fodder".
- **Calibración meta** (dev): script que baja una muestra de ratings de EasySBC de
  *mi club* para comparar y afinar pesos (no es parte del producto).
- **Solver / rendimiento**: en pools de mercado grandes el solve devuelve *feasible*
  (no siempre *optimal*) dentro del límite; el servicio lo mitiga (en posición
  primero). Revisar si merece más afinado más adelante.

## Fuentes de datos (recordatorio, de CLAUDE.md)

- **Cartas + atributos**: FUT.GG (`/api/fut/players/v2/27/`).
- **Precios PC**: EasySBC (`api-fc27.easysbc.io/players`, `Platform: PC`) — y, como
  **guía** de calibración del meta rating, su número de referencia.
- **Club y mercado visto**: extensión propia sobre la web app de EA (solo lectura).
- Límites: ≤ 1 req/s por fuente, caché, parar ante 403/429, nada de saltarse
  anti-bots (FUTBIN fuera). La extensión **solo lee**.
