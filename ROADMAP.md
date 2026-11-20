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
- **Cesiones (Hazard, Lukaku…)**: la extensión lee `loansInfo` (MATCH_LOAN = partidos
  que quedan, USER_TIME_LIMIT_LOAN = fecha de fin). Quedan fuera de SBC, evoluciones,
  plan y valor del club; el Squad Builder las excluye salvo "Incluir cesiones". Las
  temporales caducadas no se muestran.
- **Rediseño visual**: imágenes de cartas, banderas y escudos (rutas del CDN de FUT.GG
  guardadas en `cards`/`catalog`); Mi club en cuadrícula de cartas (vista Tabla
  alternativa) con insignia de cesión, Plantillas con cartas en el campo, miniaturas
  en Jugadores y resumen del club en la portada.

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
  Fuentes: stats detallados si existen, si no cara (`~` en la web).
  **Parte 2 HECHA** (rama `feat/catalog-names`): tabla `catalog` (migración 0008) con los nombres
  de 64 ligas, 164 naciones y 692 clubes, rellenada por `sync-cards` desde el listado de FUT.GG;
  `GET /catalog?kind=&q=`; nombres en `/players`; selectores de liga y nación en `/jugadores` y
  en `/plantillas` (filtran el Squad Builder); detalle de carta en la web (meta por rol, cara,
  stats detallados, PlayStyles por nombre; tabla `meta/playstyles.py`).
  **Falta**: selector de clubes (692; hace falta un buscador), meta por rol alternativo en la
  lista, ranking por rol y comparación de cartas.
- **Squad Recommendations** del club (se cubre con Squad Builder Fase A).
- **Gallery — MVP HECHO (2026-11-19)**. `gallery/points.py`: puntos = tabla por media × factor de
  rareza (calibrada con ~200 cartas observadas en soluciones de EasySBC; ≤64→20, 65‑74→35,
  75→90 … 85→2100, 88→8300; factores ×1/1,25/1,5/1,875/2,25; lo no observado, marcado
  `exact=False`). `gallery/sets.json`: 198 sets sembrados (pool por club/liga/rareza).
  `club_items.is_collected` (migración 0013; la extensión lo envía). Solver CP-SAT
  (`gallery/service.py`): rellena los N huecos al menor coste (impuesto 5 %, monedas necesarias =
  la carta más cara). `GET /gallery` y `GET /gallery/{id}/solve?grade=&complete=`; web `/galeria`.
  **Plan multi-set HECHO** (`gallery/plan.py`, `GET /gallery/plan`, pestaña «Plan de fichas»):
  una opción por set y grado; con objetivo de fichas, el menor impuesto; sin él, las máximas
  fichas dentro de los límites (saldo, impuestos, traspasos, sets). 751 fichas → ~24K de impuestos,
  496 traspasos, 34 sets (EasySBC: 26K, 556, 40). **Cartas compartidas HECHO**: una carta de club
  y de liga se compra una vez; el plan se resuelve en orden (cada set reutiliza lo comprado antes)
  y se re-planifica hasta 3 rondas mientras mejore (`make_plan`); ahorro ≈1,3K en el plan de 751
  fichas, expuesto como `saved_tax`. Resultado válido siempre en ese orden (no hay dependencias
  circulares); puede variar unos cientos entre ejecuciones (CP-SAT multihilo).
  **Marcar coleccionadas HECHO**: tabla `gallery_marks` (migración 0014; la marca manual manda
  sobre el club: True añade, False quita, None vuelve a lo que diga el club), `POST
  /gallery/collected`, `GET /gallery/{id}/cards?q=` (cartas del set con búsqueda) y en la web:
  clic en una carta de la solución, «marcar las N como coleccionadas» tras comprarlas y listado
  «Ver y marcar las cartas del set». El plan y los progresos se recalculan solos (la caché usa
  lo coleccionado como clave).
  **Pendiente**: bonus *First Owner* (magnitud sin observar), factores de rarezas aún no vistas
  (Season 1, Hall of FUT, Icons…) y puntos de 90 y ≥92.
  Historial de la decisión original (ya superada): decisión de
  Camilo: sembrar las reglas desde EasySBC como guía. Lo que SÍ es público y estático
  (`GET api-fc27.easysbc.io/gallery/sets`, 297 KB, sin cuenta): **198 sets en 10 grupos** (Rarities,
  Premier League, LaLiga, Bundesliga, Ligue 1, Serie A, Leagues, Saudi, MLS, NWSL), cada uno con
  `requiredCards` (15 en 166 sets; 4–30 en el resto), 5 grados con **umbral de puntos** (p. ej.
  Stade Brestois: D 10, C 700, B 1000, A 1600, S 2300) y fichas por grado, y un `market` con
  presupuesto y pérdida por impuestos (`/gallery/sets/<grupo>/<set>` solo repite los metadatos).
  **Lo que NO es público**: los puntos de cada carta y el pool de cada set; EasySBC los entrega
  dentro de su solución (llamadas con cuenta y cupo diario: "1 left today"). De las soluciones
  vistas se intuye `puntos = f(nivel, rareza, media)` (bronce ≤62 → 20, plata 65–73 → 35, oro
  común 75 → 90, especial 84 → 830) más un bonus de *First Owner*, pero faltaría una tabla completa
  y validada (no se puede sacar sin gastar el cupo de su cuenta, y no queremos depender de eso).
  **Para retomarla** hace falta esa tabla de puntos por (nivel, rareza, media) —por ejemplo
  observándola en el juego— y el estado de coleccionado (`isCollected` en los jugadores de EA).
  Con eso el solver es un CP-SAT de cobertura (elegir N cartas del pool con puntos ≥ umbral al
  mínimo de monedas + impuesto 5 %), que reusa `squad/market.py`. Descripción original: un modo
  de EA (se completa "en la consola") donde coleccionas jugadores en **sets por club/liga/nación**
  (15, 20 o 30 jugadores) en grados **D, C, B, A, S**; cada jugador aporta puntos (p. ej. 20 un
  59–61, 35 un 65–73, 90 un 75, 830 un 84 especial) y cada grado da fichas (13/28…). "Coleccionar"
  = comprar la carta y venderla al instante (EA la marca como coleccionada); hay bonus de
  *First Owner*. EasySBC resuelve cada set al menor coste y propone un plan: fichas objetivo,
  monedas, **pérdida por impuestos (5 %)**, nº de traspasos y de sets (`gallery/progress`,
  `user-players/collected/sync`). **Hueco de datos**: la web app de EA no tiene servicio de
  Galería (`services`: solo `EventToken`), así que no hay de dónde leer las definiciones de los
  sets (jugadores válidos, puntos por jugador, umbrales por grado, fichas por grado) ni el estado
  de coleccionado. Pista por comprobar: los jugadores de EA traen `isCollected` (visto en recompensas
  de objetivos); si el club importado lo trae, el estado coleccionado sale gratis de nuestra
  extensión. Opciones: (a) sembrar las reglas (estáticas) desde las páginas públicas de EasySBC como
  guía de desarrollo, como hicimos con el meta; (b) esperar a otra fuente. El solver sería
  un CP-SAT de cobertura de sets con coste, impuesto y first-owner (reusa `squad/market.py`).
- **Evolutions** (EN CURSO, reconocimiento hecho 2026-11-19): la web app pide
  `GET /ut/game/fc27/academy/hub/v2` al abrir Evoluciones; la respuesta trae las ~70 evoluciones
  con nombre, estado, requisitos, niveles, objetivos, mejoras y recompensas, y el cliente de EA
  expone las tablas de ids (stats, roles+/++, PlayStyles, requisitos). Todo documentado en
  `docs/superpowers/specs/2026-11-19-evoluciones-objetivos-recon.md`. **MVP HECHO** (rama
  `feat/evolutions`): la extensión reconoce `academy/hub/v2` y envía una versión reducida (sin el
  jugador de muestra) a `POST /import/evolutions` (token); tablas `evolutions` y
  `evolution_categories` (migración 0009); `GET /evolutions` (categoría, texto, caducadas) y
  `/evolutions/categories` con nombres de stat/rol/PlayStyle en español (`evolutions/enums.py`);
  página `/evoluciones` (tarjetas con mejoras, coste, caducidad y niveles). **Para ver datos
  reales**: recargar la extensión en `chrome://extensions` (dist reconstruido) y abrir
  Evoluciones en la web app. **Falta**: decodificar los requisitos de elegibilidad (`elgReqs`
  crudos), validar el formato de `currencies` con datos reales, y cruzar con tu club (qué
  cartas cumplen y cuánto sube su meta rating).
- **Objectives: MVP HECHO** (rama `feat/objectives`): la web app pide `GET /ut/game/fc27/scmp/
  objective/categories/all` al abrir FC Hub → Objetivos (6 categorías, ~53 grupos, ~209 objetivos con
  progreso `currentProgress`/`multiplier`, estado `IN_PROGRESS`/`REDEEMED`, fechas y recompensas).
  La extensión la reduce y la envía a `POST /import/objectives` (instantánea por categoría: lo que EA
  ya no lista se borra); tablas `objective_categories` y `objective_groups` (migración 0010);
  `GET /objectives` (categoría, pendientes/completados, texto, caducados) y `/objectives/categories`;
  recompensas legibles (monedas, XP, jugadores con su nombre, sobres como `Sobre #id`, fichas);
  página `/objetivos` con progreso. Solo lectura: nada de reclamar ni comprar.
  **Verificado con datos reales (2026-11-19)** usando las muestras crudas que guarda la extensión:
  EA responde a objetivos con un **array** de categorías (corregido en `toObjectivesImport`), y el
  coste de las evoluciones viene como `{funds, finalFunds, name: COINS|POINTS}` (corregido en la
  web). 9 evoluciones y 53 grupos de objetivos se ven bien en `/evoluciones` y `/objetivos`.
  **Confirmado de punta a punta (2026-11-19)**: con las tablas vacías, al recorrer Evoluciones y
  FC Hub → Objetivos la extensión envió sola 9 evoluciones y 53 grupos / 209 objetivos. La causa de
  los fallos previos era que Chrome cargaba una copia vieja de la extensión (ver `CLAUDE.md`).
  **Evoluciones con tu club: HECHO (2026-11-19, rama `feat/evolutions-club`)**: los requisitos de
  elegibilidad se decodifican (`evolutions/requirements.py`: filas `PLAYER_ATTRIBUTE`/`SCOPE`/
  `ACADEMY_PLAYER_SLOTTING`/`ADDITIONAL_TARGET_VALUE` agrupadas por `eligibilitySlot`, verificados
  contra los textos del juego: «GRL máximo: 80», «Posición: MCO O MC», «No debe ser: DFC»; los
  ids de posición son los estándar de EA y «Posición» es la preferida de la carta). Cada
  evolución muestra sus requisitos en español y `GET /evolutions/{id}/candidates` devuelve tus
  cartas aptas (o «sin poder comprobar» si falta un dato) con el **meta antes y después**:
  las mejoras por nivel se aplican con su tope a los stats detallados
  (`evolutions/projection.py`) y se recalcula con el modelo calibrado. Orden por mayor meta final
  (`sort=gain` para mayor mejora). En la web, botón «Mis cartas aptas» por tarjeta.
  **Límites**: la proyección solo cubre cartas con stats detallados (las demás salen «sin stats»;
  `make sync-club-attributes` los baja); las evoluciones de «ruta» (el jugador elige PlayStyles) no
  suben stats y salen con +0,0; los roles+/++ y los PlayStyle+ no se proyectan; el meta es del rol
  de la posición preferida.
  **Mejor evolución por carta y plan global: HECHO (rama `feat/evolutions-plan`)**:
  `GET /evolutions/for-card/{item_id}` (las evoluciones activas que esa carta puede tomar, por mayor
  meta final) y `GET /evolutions/plan?min_after=` (asignación óptima con CP-SAT: cada evolución y
  cada carta una sola vez, maximizando la mejora total de meta; solo cartas aptas con stats
  detallados). `ClubEvaluator` carga el club una vez (0,2 s para 9 evoluciones × 193 cartas). En la
  web, botón «Plan para tu club» en `/evoluciones` con «Meta final mínimo» (por defecto 70): con tu
  club, 7 de 9 evoluciones y +58,8 de meta. **Falta**: vista por carta en la web (el endpoint ya
  existe), evoluciones repetibles (hoy cada una se usa una vez) y tener en cuenta el coste en
  monedas/FC Points.
  **Nombres de sobres: HECHO (rama `feat/pack-names`)**: la web app trae en su tabla de traducciones
  (`services.Localization`) las claves `FUT_STORE_PACK_<id>_NAME` (~1.140 sobres, en español). La
  extensión las lee de memoria local —sin peticiones a EA— al iniciar la importación automática y las
  envía a `POST /import/packs`; se guardan en `catalog` (`kind='pack'`) y las recompensas de
  `/objetivos` muestran el nombre real («Sobre de oro raro») en vez de `Sobre #id`. Hay que
  copiar el `dist` a la copia de Chrome y recargar la extensión (ver `CLAUDE.md`).
  **Falta**: campaña/pase de temporada (`activeCampaign`, otra llamada), fichas con nombre y avisos
  de objetivos por caducar.
- **Vistas de valor: HECHAS (parte 1)** (rama `feat/value-views`): `GET /value/bargains`
  ("hidden profit": percentil de meta − percentil de precio dentro del rol, entre cartas 75+;
  filtros por rol/posición/media/precio) y `GET /value/fodder` (las N cartas más baratas por
  media, para SBC); página web `/valor` con pestañas Chollos / Fodder. Usa el precio
  `easysbc:market` (suelo de 650). **Falta**: cruzar con tu club (qué cartas tuyas valen más
  de lo que crees, qué sobra como fodder), tendencia de precios y alertas.
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
