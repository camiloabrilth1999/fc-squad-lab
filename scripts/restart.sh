#!/usr/bin/env bash
# Reinicia la API y la web (borra la caché de Next) para ver los últimos cambios.
# Postgres no se toca. Uso: bash scripts/restart.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Parando API y web…"
pkill -f "uvicorn fcsl_api" 2>/dev/null
pkill -f "next dev" 2>/dev/null
pkill -f "next-server" 2>/dev/null
sleep 2
rm -rf "$ROOT/apps/web/.next"

bash "$ROOT/scripts/start.sh"
