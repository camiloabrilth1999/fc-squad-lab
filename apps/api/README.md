# fcsl-api

API de FC Squad Lab. Ver el README de la raíz.

## Endpoints de solve

- `POST /solve`: resuelve el pool pedido (`pool`). `time_limit_s` (0 < t ≤ 60, por defecto 10) es el tiempo total de reloj del servicio: poda, modelo, solve y métricas.
- `POST /solve/pools`: resuelve club, ambos y mercado (solo mercado si no hay cartas del club). `time_limit_s` se aplica **a cada pool**, así que la respuesta puede tardar hasta 3 × `time_limit_s`.
