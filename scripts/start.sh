#!/usr/bin/env bash
# Arranca todo lo necesario (Postgres, API y web) si no está ya en marcha.
# Uso: bash scripts/start.sh        (se puede repetir sin problema)
source ~/.nvm/nvm.sh >/dev/null 2>&1
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG=/usr/lib/postgresql/16/bin/pg_ctl
PGDATA="$HOME/pgdata-fcsl"

up() { curl -s -o /dev/null --max-time 2 "$1"; }

if ! $PG -D "$PGDATA" status >/dev/null 2>&1; then
  echo "Arrancando Postgres…"
  mkdir -p "$PGDATA/sock"
  $PG -D "$PGDATA" -o "-p 5544 -k $PGDATA/sock" -l "$PGDATA/log.txt" start >/dev/null
fi

if ! up http://localhost:8787/health; then
  echo "Arrancando la API (8787)…"
  (cd "$ROOT/apps/api" && setsid nohup uv run uvicorn fcsl_api.main:app --port 8787 \
    >/tmp/fcsl-api.log 2>&1 < /dev/null &)
fi

if ! up http://localhost:3030; then
  echo "Arrancando la web (3030)…"
  (cd "$ROOT/apps/web" && setsid nohup npm run dev -- -p 3030 \
    >/tmp/fcsl-web.log 2>&1 < /dev/null &)
fi

for _ in $(seq 1 40); do
  up http://localhost:8787/health && up http://localhost:3030 && break
  sleep 1
done
up http://localhost:8787/health && echo "API lista: http://localhost:8787" || echo "API no responde (mira /tmp/fcsl-api.log)"
up http://localhost:3030 && echo "Web lista: http://localhost:3030" || echo "Web no responde (mira /tmp/fcsl-web.log)"
