# fcsl-api

API de FC Squad Lab. Ver el README de la raíz.

## Endpoints de solve

- `POST /solve`: resuelve el pool pedido (`pool`). `time_limit_s` (0 < t ≤ 60, por defecto 10) es el tiempo total de reloj del servicio: poda, modelo, solve y métricas.
- `POST /solve/pools`: resuelve club, ambos y mercado (solo mercado si no hay cartas del club). `time_limit_s` se aplica **a cada pool**, así que la respuesta puede tardar hasta 3 × `time_limit_s`.

## Ingesta de datos

Requiere Postgres arriba y migrado (`make db-start db-migrate`). Cada sincronización respeta 1 petición/s y registra una fila en `sync_runs` (`ok`, `partial` o `failed`).

- `make sync-cards [ARGS="--max-pages N"]`: cartas desde FUT.GG (completa ≈ 15–20 min).
- `make sync-prices [ARGS="--max-pages N"]`: precios PC desde EasySBC (`easysbc:market` y `easysbc:sbc`).
- `make data-status`: nº de cartas, precios por fuente y última sincronización por tipo.

`--max-pages N` cuenta peticiones, no páginas de resultados: si FUT.GG particiona por media, parte de ese presupuesto se gasta bajando por los rangos y devuelve pocas cartas (con 3, unas 30; con 1, ninguna). Es solo para pruebas rápidas: si deja páginas sin recorrer, la fila de `sync_runs` queda `partial` (o `failed` si no guardó nada) con el motivo en `error`. Las respuestas se cachean 6 h en `apps/api/var/cache/<fuente>`; `--no-cache` fuerza la descarga. Un sync de precios borra las filas `easysbc:*` viejas de cada carta vista (cambio de fuente o sin precio utilizable).

Precio efectivo (`fcsl_api.prices.effective_prices`): `ea-session` con menos de 24 h; si no, `easysbc:market`; si no, `easysbc:sbc`; si no, ausente.

## Importación desde la sesión de EA

Los usa la extensión de Chrome (solo lectura). Requieren `FCSL_IMPORT_TOKEN` (entorno o `apps/api/.env`) y la cabecera `X-FCSL-Token`: sin token configurado devuelven 503; con token ausente o incorrecto, 401. Cuerpos de más de 2 MB → 413.

- `POST /import/club`: `{location, items, duplicate_item_ids}` → upsert en `club_items` (solo jugadores) y fila `club` en `sync_runs`.
- `POST /import/market`: `{observations:[{resourceId, buyNowPrice, seenAt}]}` → mínimo por recurso en `prices` (`source="ea-session"`, `platform="PC"`, `captured_at` = último `seenAt`) y fila `market` en `sync_runs`.
- `POST /import/raw`: `{url, body}` → guarda el JSON en `apps/api/var/samples/` (máx. 50 archivos, 2 MB por petición) para aprender los formatos reales.

## Club

La importación es pasiva y no detecta cartas vendidas o descartadas.

- `GET /club`: lista y resumen; `max_age_days` (por defecto 30) oculta las cartas no vistas en ese plazo, `0` muestra todas. Cada fila trae `seen_at`.
- `POST /club/forget` (mismo token que `/import`): `{older_than_days: N≥1}` borra las cartas no vistas en N días (o nunca vistas) → `{deleted: n}`.
