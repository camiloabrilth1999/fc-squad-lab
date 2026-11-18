# Plan: replicar EasySBC (estado actual, huecos y Squad Builder)

Fecha: 2026-11-18 · Basado en recon en vivo de https://www.easysbc.io (my-club,
squad-builder, players) y un health-check de nuestra app.

## Intención y porqué

Replicar las funciones de EasySBC.io sobre nuestros propios datos (club real
importado + datos de EA capturados) para poder **cancelar la suscripción de
EasySBC** sin perder sus funciones. Hoy ya resolvemos SBC mejor que ellos en lo
nuestro (datos reales de EA, fuera de posición); falta el resto de su producto,
cuyo centro es el **meta rating** y el **Squad Builder**.

## Estado actual (verificado hoy, en verde)

- **Extensión**: importa el club desde la web app de EA.
- **API (FastAPI + OR-Tools CP-SAT)**:
  - `/club` con precios (`price_source = easysbc:market`) y `value`.
  - `/sbc`: 55 retos reales capturados (OPEN + un clic).
  - `solve` con pool club/mercado/ambos: fuera de posición, química, valoración de
    equipo, requisitos (incl. RATING_PLAYERS y topes de un clic).
  - 337 tests + ruff en verde; benchmark de rendimiento pasa.
- **Web (Next.js)**: "Mi club" y página de SBC conectada al backend (3030 OK).

## EasySBC: funciones (lo que replicamos)

Navegación: **SBC · Players · Squad Builder · Gallery · Evolutions · Objectives ·
My Club**.

- **Players / Meta Ratings DB**: 21.000+ cartas, cada una con un **meta rating por
  rol** (p. ej. "Falseback LB 86.0 A", "Box Crasher CDM 82.8 B", "Adv. Fwd. ST
  79.8") + stats (PAC/SHO/PAS/DRI/DEF/PHY), skill moves, pie malo, precio. El meta
  rating está atado al **rol** (sistema de roles de EA FC), no solo a la posición.
- **Squad Builder** ("the world's only AI squad builder"): construir la mejor
  plantilla por **meta rating + química alta** con:
  - formación elegida o **"Best Formation"** (la elige por ti),
  - **presupuesto** (precio máximo del equipo),
  - **fuente**: mercado / club / iconos,
  - **filtros**: país, liga, club (incluir) y "must include",
  - **evento en vivo**, manager (nación/liga),
  - **jugadores fijados**: construye alrededor de tus favoritos.
- **My Club**: overview con el XI activo, **meta rating por carta + meta del equipo
  + química + nota (A/B/…)**, recomendaciones ("best possible squad"), mis
  jugadores, "hidden profit", "SBC fodder".
- **Gallery**: soluciones a los sets de galería.
- **Evolutions**, **Objectives**: tracking/planificación.

## Qué tenemos vs qué falta

| Función EasySBC | Nosotros |
|---|---|
| SBC solver + soluciones | ✅ (mejor: datos reales de EA, fuera de posición) |
| Precios de mercado | ✅ (`easysbc:market`) |
| Import + overview del club | ✅ parcial (sin meta rating ni notas por carta) |
| **Meta rating por rol** | ❌ — la base que falta |
| **Squad Builder** | ❌ |
| "Best possible squad" del club (recommendations) | ❌ (es el squad builder con pool=club) |
| Players DB (meta ratings) | ❌ |
| Gallery solutions | ~ (tenemos SBC; falta el modo galería) |
| Evolutions / Objectives | ❌ |
| Hidden profit / SBC fodder | ~ (tenemos `value`/precio; falta la vista) |

## Fase siguiente: Squad Builder

**Objetivo**: dada una formación (o la mejor), **maximizar el meta rating** del XI
con **química ≥ objetivo**, dentro de un **presupuesto**, desde **club/mercado/
ambos**, con filtros (país/liga/club, must-include) y jugadores fijados.

**Reutiliza casi todo el solver actual**: el modelo CP-SAT ya cubre huecos,
química, único por carta, coste y fuera de posición. El cambio central es el
**objetivo**: pasar de "minimizar coste cumpliendo requisitos" a **"maximizar
Σ meta_rating" con Σ coste ≤ presupuesto** (y química como restricción). "Best
formation" = resolver varias formaciones y quedarse con la mejor.

### El punto crítico: de dónde sale el meta rating

Es el único dato base que no tenemos y el que condiciona toda la fase. EasySBC lo
calcula por rol con un algoritmo propietario (no replicable exactamente). Opciones:

- **A — Meta rating propio** (heurística por rol a partir de stats + playstyles +
  rol): totalmente independiente (encaja con la meta de no depender de EasySBC),
  pero no coincidirá con sus números y es trabajo de modelado (pesos por rol).
- **B — Tomar el meta rating de la API de EasySBC** (igual que ya tomamos los
  precios `easysbc:market`): rápido y coincide, pero depende de su API (fragilidad;
  va contra la independencia; aunque ya dependemos de ella para precios).
- **C — Híbrido (recomendado)**: empezar con una **heurística propia por rol**
  sencilla para desbloquear el squad builder de punta a punta ya, y después
  (si quieres) contrastarla/afinarla contra la de EasySBC. Entregamos valor pronto
  y mantenemos la puerta abierta a la independencia total.

**Recomendación: C.** Primero una heurística propia por rol (transparente y
nuestra), con el squad builder funcionando end-to-end; afinamos los pesos después.

### Entregable de la fase

- **Meta rating** por carta/rol (según la decisión A/B/C) + endpoint para
  consultarlo.
- **Solver**: objetivo "maximizar meta" con presupuesto; "best formation".
- **API**: `POST /squad/build` (formación|best, budget, pool, filtros, fijados) →
  mejor XI con meta/química/coste/compras.
- **Web**: página Squad Builder (formación, presupuesto, filtros, "Build").

## Orden propuesto (replicación completa)

1. **Squad Builder** (esta fase): meta rating → solver "maximiza meta" → API → web.
2. **Players DB** (reusa el meta rating) + **recommendations** (best XI del club).
3. **Gallery** (modo soluciones de galería sobre el solver de SBC).
4. **Evolutions** y **Objectives** (capturar datos de EA + tracking).
5. Vistas de valor: **hidden profit** / **SBC fodder**.

## Decisión abierta (tuya)

Antes de diseñar el detalle del Squad Builder: **¿de dónde sacamos el meta rating
— A (propio), B (API de EasySBC) o C (híbrido, recomendado)?** Cambia el modelo y
cuánto dependemos de EasySBC.
