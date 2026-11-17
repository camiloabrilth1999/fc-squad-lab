# FC Squad Lab — Diseño

Fecha: 2026-11-16 · Estado: borrador para aprobación · Nombre provisional (la marca la elige Camilo).

## 1. Intención y por qué

Camilo quiere su propia web, **solo para su uso personal**, para armar sus equipos de EA FC 27 Ultimate Team con su club real: resolver SBC, construir plantillas, planificar evoluciones y objetivos. Hoy usa EasySBC, que hace todo esto en su servidor y lo raciona con "créditos de IA" diarios. Quiere **todas esas funciones, mejor optimizadas y mejor hechas, con una marca propia**, sin límites ni dependencia de un servicio ajeno.

Referencia de producto: EasySBC (analizado con REA el 2026-11-16). Se replican las *ideas*, no el código ni la marca.

## 2. Objetivos, no-objetivos y anti-objetivos

**Objetivos**
- Solver de SBC exacto (no heurístico) que use el club de Camilo y devuelva varias soluciones por SBC: solo club, club + mercado, solo mercado.
- Constructor de plantillas con química FC 27 y "mejor plantilla con mi club".
- Planificador de evoluciones (cadenas) y de objetivos.
- Sin créditos ni límites; respuestas en segundos.
- Importación del club en un clic desde la web app de EA.

**No-objetivos (por ahora)**
- Multiusuario, cuentas, pagos, app móvil, idiomas además del español.
- Mostrar historial de precios o gráficas de mercado.
- Publicar la web en Internet para terceros.

**Anti-objetivos (sería un fracaso aunque funcione)**
- Que EA pueda detectar automatización y bloquee la cuenta de Camilo. La extensión **solo lee** lo que la web app ya cargó o carga cuando Camilo navega; nunca compra, puja, lista ni busca en el mercado por su cuenta.
- Copiar código, textos, imágenes o marca de EasySBC.
- Raspar agresivamente webs de precios (muchas peticiones, saltarse protecciones).

## 3. Restricciones

- Corre en el Mac de Camilo (macOS, Apple Silicon). Sin Homebrew en este usuario: dependencias vía Docker Desktop o instaladores propios. Despliegue opcional futuro en su VPS con Dokploy.
- Una sola plataforma de precios: **PC** (Camilo juega en Windows; el mercado de PC es distinto del de consolas). La extensión se usa en el Chrome donde Camilo abra la web app (Mac o Windows); la app corre en el Mac.
- Datos de jugadores y precios vienen de fuentes externas que pueden cambiar sin aviso → todo acceso externo va detrás de adaptadores reemplazables.

## 4. Enfoques considerados (fuente de datos)

| Enfoque | Qué es | Pros | Contras |
|---|---|---|---|
| A. Solo sesión EA | Extensión propia lee club y lo que Camilo ve en el mercado | Datos propios, gratis | Sin precios de lo que no miras; automatizar el mercado arriesga baneo |
| B. Solo webs públicas | Base de cartas y precios de FUT.GG/FUTBIN | Cobertura completa | Va contra sus términos; no da tu club |
| **C. Híbrido (elegido)** | Club desde extensión propia de solo lectura; base de cartas y precios de una fuente pública, consultada poco y con caché | Club exacto + precios completos, sin tocar el mercado de EA | Dependencia de una fuente de precios que puede cambiar |

**Elegido: C**, por Camilo, 2026-11-16.

**Actualización 2026-11-17 (fuentes concretas, decididas por Camilo tras explorar):**
- **Base de cartas:** API pública de listado de jugadores de FUT.GG (`/api/fut/players/v2/27/`). Su `robots.txt` pide no usar `/api/*`; Camilo asume ese riesgo para uso personal local.
- **Precios PC:** API pública de EasySBC (`api-fc27.easysbc.io/players`, cabecera `Platform: PC`, campo `priceInfo`). Sus términos (§26) prohíben la extracción; Camilo asume ese riesgo para uso personal local.
- **Tu sesión de EA (extensión):** club, almacén, lista de transferencias, SBC y los precios del mercado que Camilo ve al buscar a mano.
- **Límites que no se negocian:** como mucho 1 petición/s por fuente, caché, refresco cada varias horas, parar ante 403/429, y **nunca** saltarse protecciones anti-bots (FUTBIN y la ruta de precios de FUT.GG están tras Cloudflare → no se usan).
- Clave común: `resource_id` de EA = `eaId` de FUT.GG = `resourceId` de EasySBC.

## 5. Arquitectura (decisiones del diseñador; Camilo puede cambiarlas)

```
 Chrome (web app EA) ──extensión MV3 (solo lectura)──▶  API local
                                                         │
 Fuente pública de cartas/precios ◀── job de ingesta ────┤
                                                         ▼
  Web (Next.js) ◀──────────── API (FastAPI, Python) ── Postgres
                                   │
                                   └── Solver (OR-Tools CP-SAT, en proceso)
```

- **Web**: Next.js (App Router) + TypeScript + Tailwind. Identidad visual propia (por definir con la marca).
- **API + solver**: Python 3.12, FastAPI, Google OR-Tools CP-SAT. Python porque OR-Tools es más maduro ahí y el solver es el corazón del producto.
- **Base de datos**: Postgres 16. Todo con Docker Compose (`web`, `api`, `db`, `worker`).
- **Extensión**: Chrome MV3, content script solo en `https://www.ea.com/*ea-sports-fc/ultimate-team/web-app/`. Envía al API con un token personal fijo. La URL del API es configurable: `http://localhost:<puerto>` si la web app se abre en el Mac, o la IP del Mac en la red de casa si se abre en el Chrome de Windows (decisión del diseñador). Plan B sin red: la extensión descarga un JSON del club que se sube a mano en la web.
- **Worker de ingesta**: proceso programado que actualiza base de cartas y precios.

Monorepo en `~/Code/Personal/fc-squad-lab/` con `apps/web`, `apps/api`, `apps/extension`, `packages/`, `docs/`.

## 6. Modelo de datos (núcleo)

- **Card** (una carta concreta de UT): `resource_id` (id de item EA), `asset_id` (id del jugador base), nombre, media, posición preferida y alternativas, liga, club, nación, rareza/versión, si es icono/héroe, estadísticas, playstyles. Varias Card comparten `asset_id` (versiones especiales).
- **Price**: `resource_id`, plataforma, precio, fecha de captura, fuente. Solo se guarda el último + hora de captura.
- **ClubItem** (cartas de Camilo): `item_id` EA, `resource_id`, intransferible, dónde está (club, almacén SBC, lista de transferencias, plantilla activa), duplicado, cedido, fecha de importación, `last_sale_price` si EA lo da.
- **SbcSet / SbcChallenge**: conjunto, retos, requisitos estructurados (ver §7.1), recompensa, caducidad, repetible.
- **Solution**: reto, estrategia, lista de cartas por posición, coste, química, media, origen de cada carta.
- **Evolution / EvolutionChain**, **Objective / ObjectivePlan**: fases 4–5.

## 7. Funciones por fase

Cada fase termina usable antes de empezar la siguiente.

### Fase 0 — Cimientos
Monorepo, Docker Compose, API con salud, web vacía con navegación, esquema inicial de DB, CI local (tests + lint).

### Fase 1 — Datos
1. **Base de cartas y precios**: adaptador `CardSource` + `PriceSource`, primera implementación contra FUT.GG (o la que mejor funcione al probarla), con caché, límite de ~1 petición/seg y refresco cada pocas horas. Si la fuente falla, la app sigue con los últimos datos y lo muestra.
2. **Extensión de importación**: lee club, almacén SBC, lista de transferencias y plantilla activa usando la propia web app (sus servicios internos / respuestas que ya recibe); **nunca** llama al mercado. Botón "Importar club" + importación automática al abrir el club. Sube a `/import/club`.
3. **Mi club**: listado filtrable (media, liga, nación, club, posición, intransferible, duplicado, ubicación) con valor estimado del club.

### Fase 2 — Solver de SBC (MVP)
1. **Retos**: carga de SBC activos. Los requisitos se guardan estructurados. Fuente principal (decisión del diseñador): la extensión lee los conjuntos y requisitos que la web app de EA ya carga cuando Camilo abre la pestaña de SBC (solo lectura, son datos oficiales y exactos). Respaldo: la fuente pública si los expone, y alta manual con formulario como último recurso.
2. **Modelo de optimización** (CP-SAT):
   - Variables: carta *c* en posición *p* (solo posiciones donde la carta puede jugar; FC 27 permite cambiar a posiciones alternativas sin penalización de química).
   - Restricciones soportadas: nº de jugadores, media mínima de equipo (fórmula oficial de media con corrección por encima de la media), química mínima total y por jugador, mín/máx/exacto de jugadores de liga/nación/club, nº de ligas/naciones/clubes distintos (mín/máx), "mismo" liga/nación/club (mín por grupo), rareza (oro/plata/bronce, raro/común, especiales tipo TOTW/TOTS), media mínima por jugador, jugadores incluidos/excluidos.
   - Química FC 27 (umbral por club, liga y nación; iconos y héroes según sus reglas) modelada con variables enteras auxiliares.
   - Objetivo configurable: (a) mínimo coste en monedas. Valor por defecto de cada carta (decisión del diseñador, configurable): intransferibles propias = 0; transferibles propias = 95 % de su precio (lo que obtendrías vendiéndola tras el 5 % de impuesto de EA), con un pequeño descuento extra para duplicados y cartas del almacén SBC; cartas de mercado = precio de PC. El mercado se limita a cartas con precio conocido; (b) máximo uso de intransferibles/duplicados, (c) mínimo número de compras.
   - Pools: `club`, `club+mercado`, `mercado`.
   - Límite de tiempo por resolución (p. ej. 10 s) y devuelve la mejor encontrada + si es óptima.
3. **Pantalla de reto**: campo con la solución, coste, química, media, origen por carta, alternativas por hueco (las 2 mejores propias y 2 de mercado) y re-resolver fijando cartas.
4. **Conjuntos repetibles**: resolver N veces seguidas sin reutilizar cartas.

### Fase 3 — Constructor de plantillas
Formaciones, química en vivo, búsqueda de jugadores, y "mejor plantilla con mi club" (mismo motor: maximizar media/química/meta-rating con restricciones de formación).

### Fase 4 — Evoluciones
Catálogo de evoluciones activas con requisitos; para cada carta del club, qué evoluciones puede hacer y la mejor cadena (búsqueda sobre requisitos encadenados).

### Fase 5 — Objetivos y extras
Planificador de objetivos (qué plantillas jugar para avanzar varios a la vez), galería de soluciones guardadas, comparador de jugadores y un "meta rating" propio (fórmula transparente a partir de estadísticas y playstyles, ajustable).

## 8. Preguntas abiertas para Camilo

1. ~~Plataforma de precios~~ → resuelto: PC.
2. **Marca**: nombre e identidad (pueden esperar a la fase 3; mientras, nombre provisional).
3. ~~Dónde corre~~ → resuelto: en el Mac por ahora (VPS más adelante, si hace falta).

## 9. Lo que queda a criterio del constructor

- Proveedor concreto de la fuente pública y su formato, tras probarlo.
- Esquema SQL detallado, librería de UI, estructura de componentes.
- Cómo leer exactamente los datos dentro de la web app de EA (servicios internos vs. interceptar respuestas), siempre en solo lectura.
- Formulación exacta de química y media en CP-SAT, validada contra ejemplos reales del juego.
- Calidad: tests del solver con SBC reales conocidos (solución válida y coste ≤ referencia).

## 10. Criterio de éxito

- Camilo importa su club en un clic.
- Resuelve un SBC típico con su club en < 10 s, con una solución válida que EA acepta.
- Coste igual o menor que el que mostraría EasySBC para el mismo SBC y club.
- No hay ninguna acción automática en el mercado de EA.
