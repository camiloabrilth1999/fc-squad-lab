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

Precio efectivo (`fcsl_api.prices.effective_prices`): `ea-session` con menos de 24 h; si no, `easysbc:market`; si no, `easysbc:sbc`; si no, ausente.
