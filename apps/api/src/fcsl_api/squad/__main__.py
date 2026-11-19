"""CLI del Squad Builder: python -m fcsl_api.squad scan --formation 442 --budget 200000.

Baja los stats detallados (FUT.GG, ≤ 1 req/s, con caché) de los candidatos de mercado
de una formación y presupuesto, para que `POST /squad/build` con `pool: both` los use.
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from fcsl_api.db import get_session
from fcsl_api.ingest import futgg
from fcsl_api.ingest.futgg_detail import fetch_card_attributes
from fcsl_api.ingest.http import make_client
from fcsl_api.ingest.store import upsert_card_attributes
from fcsl_api.models_db import CardAttributes
from fcsl_api.sbc import formations
from fcsl_api.squad.market import PER_POSITION, market_candidates

CACHE = Path(__file__).resolve().parents[3] / "var" / "cache"


def scan(formation: str, budget: int, per_position: int, limit: int | None) -> int:
    slots = formations.slots_for(formation)
    with get_session() as session:
        cands = market_candidates(
            session, set(slots), budget, datetime.now(UTC), per_position=per_position
        )
        have = set(session.scalars(select(CardAttributes.resource_id)))
        todo = [c for c in cands if c.resource_id not in have][:limit]
        print(f"candidatos: {len(cands)}, sin stats: {len(todo)}", flush=True)
        client = make_client(futgg.BASE_URL, cache_dir=CACHE / "futgg")
        saved = 0
        try:
            for n, card in enumerate(todo, 1):
                attrs = fetch_card_attributes(client, str(card.asset_id), card.resource_id)
                if attrs:
                    upsert_card_attributes(session, card.resource_id, attrs)
                    saved += 1
                if n % 25 == 0:
                    print(f"  {n}/{len(todo)}", flush=True)
        finally:
            client.close()
    print(f"guardados: {saved}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fcsl_api.squad")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--formation", default=formations.DEFAULT_FORMATION)
    s.add_argument("--budget", type=int, required=True)
    s.add_argument("--per-position", type=int, default=PER_POSITION)
    s.add_argument("--limit", type=int, default=None, help="máximo de fichas a bajar")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    return scan(args.formation, args.budget, args.per_position, args.limit)


if __name__ == "__main__":
    sys.exit(main())
