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
- **Squad Builder — Fase A (solo club)**: "mejor XI de tu club" maximizando
  meta + química (la función "best possible squad" de EasySBC). Reusa el solver;
  objetivo = maximizar Σ meta en vez de minimizar coste.

## Pendiente / aparcado (no perder)

- **Squad Builder — Fase B (mercado + filtros)**: sugerir compras de cualquier carta
  con presupuesto, fuente (mercado/club/iconos), filtros (país/liga/club, must-include),
  "best formation", jugadores fijados. **Requiere** la DB completa de players.
- **Players DB** (~21k cartas con meta rating por rol + stats + precio).
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
