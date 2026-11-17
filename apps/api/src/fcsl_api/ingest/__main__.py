"""CLI de ingesta: python -m fcsl_api.ingest {sync-cards,sync-prices,status}."""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fcsl_api.db import get_session
from fcsl_api.ingest import easysbc, futgg
from fcsl_api.ingest.http import make_client
from fcsl_api.ingest.sync import sync_cards, sync_prices
from fcsl_api.models_db import Card, Price, SyncRun

API_DIR = Path(__file__).resolve().parents[3]  # apps/api, sin depender del CWD
CACHE_DIR = API_DIR / "var" / "cache"


def cache_dir(source: str, no_cache: bool) -> Path | None:
    return None if no_cache else CACHE_DIR / source


def _print_run(run: SyncRun) -> int:
    print(f"{run.kind}: {run.status}, {run.items} filas" + (f" ({run.error})" if run.error else ""))
    return 0 if run.status == "ok" else 1


def _status(session: Session) -> int:
    print(f"cartas: {session.scalar(select(func.count()).select_from(Card))}")
    print("precios por fuente:")
    counts = session.execute(
        select(Price.platform, Price.source, func.count()).group_by(Price.platform, Price.source)
    ).all()
    for platform, source, n in counts or []:
        print(f"  {platform} {source}: {n}")
    if not counts:
        print("  (ninguno)")
    print("última sincronización por tipo:")
    last = session.scalars(select(SyncRun).order_by(SyncRun.started_at.desc(), SyncRun.id.desc()))
    seen: set[str] = set()
    for run in last:
        if run.kind in seen:
            continue
        seen.add(run.kind)
        print(f"  {run.kind}: {run.status}, {run.items} filas, {run.finished_at}")
        if run.error:
            print(f"    {run.error}")
    if not seen:
        print("  (ninguna)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fcsl_api.ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("sync-cards", "sync-prices"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--max-pages", type=int, default=None)
        cmd.add_argument("--no-cache", action="store_true", help="ignora la caché de disco")
    sub.add_parser("status")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with get_session() as session:
        if args.command == "status":
            return _status(session)
        if args.command == "sync-cards":
            client = make_client(futgg.BASE_URL, cache_dir=cache_dir("futgg", args.no_cache))
            sync = sync_cards
        else:
            client = make_client(
                easysbc.BASE_URL,
                headers=easysbc.HEADERS,
                cache_dir=cache_dir("easysbc", args.no_cache),
            )
            sync = sync_prices
        try:
            return _print_run(sync(session, client, max_pages=args.max_pages))
        finally:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
