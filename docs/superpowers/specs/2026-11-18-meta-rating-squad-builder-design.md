# Diseño: Meta rating propio + Squad Builder (Fase A, club)

Fecha: 2026-11-18. Contexto en `ROADMAP.md` y en
`docs/superpowers/specs/2026-11-18-replicar-easysbc-plan.md`.

## Intención y porqué

Replicar lo que hace EasySBC pero con **datos y cálculo propios**, para poder
cancelar su suscripción. El núcleo es el **meta rating** (cómo de buena es una carta
en un rol, 0–99.9) y, encima, el **Squad Builder**. Empezamos por "la mejor
plantilla de tu club" (lo más valioso y achievable; la función "best possible squad"
de EasySBC).

## Objetivos

- **Meta rating propio** por `(carta, rol)`: transparente (sabemos por qué puntúa
  así), versionado y ajustable; sin depender de la API de EasySBC en el producto.
- **Squad Builder Fase A**: dado tu club y una formación (o la mejor), devolver el
  **XI que maximiza el meta rating** cumpliendo una **química objetivo**.

## No-objetivos (ahora)

- No clonar los números exactos de EasySBC (sus pesos son secretos).
- No la DB completa de ~21k cartas (eso es Fase B / Players DB).
- No mercado/compras ni filtros avanzados (Fase B).
- No evoluciones/objetivos/galería (fases posteriores).

## Anti-objetivos (fallo aunque funcione)

- Que el producto dependa de la API de EasySBC para el meta rating.
- Saltarse límites o anti-bots de cualquier fuente.

## Restricciones

- Fuentes (CLAUDE.md): cartas/atributos de **FUT.GG**; precios de **EasySBC**
  (`/players`, `Platform: PC`); club de la **extensión** (solo lectura). ≤ 1 req/s,
  caché, parar ante 403/429.
- Solo API PEP8 de OR-Tools. `make check` verde antes de cada commit.

## En qué se basa el meta rating (de la página pública de EasySBC)

Por **rol**, considera: **stats detallados** (los ~35, no solo los 6 de la cara),
**PlayStyles(+)** (los relevantes al rol dan un plus fuerte), **AcceleRATE**
(explosivo/controlado/largo) y **WF/SM**. Publican, por rol, los **"Top Stats"** y
los **"Best PlayStyles+"** (p. ej. Advanced Forward ST → Aceleración, Velocidad
punta, Definición, Agilidad, Equilibrio). Los **pesos** no son públicos. Caso guía:
Lewandowski (poca velocidad) saca meta baja pese a OVR alto → la velocidad pesa
mucho en ataque.

## Enfoques considerados (meta rating)

- **A — Propio desde cero**: independiente, pero más trabajo y sin referencia.
- **B — API de EasySBC**: rápido y coincide, pero dependemos de ellos (anti-objetivo).
- **C — Propio, calibrado con la metodología pública de EasySBC (elegido)**: pesos
  nuestros, *sembrados* desde los "top stats por rol" públicos; EasySBC solo como
  **guía de calibración** en desarrollo (no en el producto). Independiente y con
  referencia para afinar.

Decisión de Camilo: **C**. Nuestro meta rating propio; EasySBC como guía para afinar.

## Decisiones de diseño

### Datos (atributos detallados)

- **Club (Fase A)**: capturar los atributos detallados **de EA** (la extensión ya
  lee los ítems del club; el `attributeArray` + PlayStyles + AcceleRATE están en el
  mismo objeto) → se amplía la importación y el modelo para guardarlos. ~179 cartas,
  sin coste extra de red. (Alternativa descartada por ahora: detalle por carta de
  FUT.GG, una llamada por carta.)
- Para Fase B (DB completa) ya se verá (detalle masivo de FUT.GG/EA) — aparcado.

### Meta rating

- Módulo **puro** (como `chemistry.py`): `meta_rating(card_attrs, role) -> float`
  0–99.9, verificable con tests y fixtures, sin tocar BD.
- Tabla **rol → (atributos clave con pesos, PlayStyles+ relevantes, AcceleRATE
  preferido)**, sembrada desde la página pública de EasySBC; versionada en el repo.
- Fórmula = suma ponderada de los atributos clave del rol (normalizados) + bonus por
  PlayStyle+ relevantes + ajuste por AcceleRATE + aporte menor de WF/SM; escala a
  0–99.9. Tiers (S/A+/A/B+/B) por percentiles sobre el conjunto considerado.
- Meta por `(carta, rol)`; se expone el **mejor rol** de la carta.

### Squad Builder Fase A (solver)

- Reusa el modelo CP-SAT actual. Cambia el **objetivo**: de "minimizar coste" a
  **"maximizar Σ meta_rating"** del XI, con **química ≥ objetivo** como restricción
  (ya la tenemos) y pool = club. Fuera de posición ya resuelto.
- El meta de cada hueco usa el **rol** de la posición del hueco (o el mejor rol de la
  carta compatible). "Best formation" = resolver varias formaciones y quedarse con la
  de mayor meta total (iteración sobre formaciones conocidas).

### Entregables

- API: meta rating por carta/rol; `POST /squad/build` (formación|best, química
  objetivo, pool=club) → XI con meta por carta, meta total, química, coste.
- Web: página "Squad Builder" (formación, química objetivo, botón construir) +
  meta rating visible en "Mi club".

### Calibración (dev, no producto)

- Script que baja de EasySBC (`/players`, que ya usamos para precios y que
  probablemente trae su meta) una muestra de *mi club* y la compara con la nuestra,
  para ajustar los pesos. No se envía al producto.

## Qué queda al constructor

- Orden sugerido: (1) módulo meta rating puro + tabla de roles/pesos semilla;
  (2) ampliar captura de atributos del club; (3) solver "maximiza meta" + endpoint;
  (4) web. TDD en cada paso; `make check` verde.
- Afinar pesos con el script de calibración tras tener el end-to-end.
