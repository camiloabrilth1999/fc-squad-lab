"""CLI de calibración del meta (desarrollo): python -m fcsl_api.meta {fetch-sample,report}."""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import select

from fcsl_api.db import get_session
from fcsl_api.ingest import futgg
from fcsl_api.ingest.futgg_detail import fetch_card_attributes
from fcsl_api.ingest.http import make_client
from fcsl_api.ingest.store import upsert_card_attributes
from fcsl_api.meta.calibration import (
    FAMILIES,
    build_dataset,
    fit_all,
    fit_family,
    load_reference,
    sample_resource_ids,
)
from fcsl_api.models_db import Card, CardAttributes

API_DIR = Path(__file__).resolve().parents[3]
CACHE = API_DIR / "var" / "cache"


def fetch_sample(per_family: int, limit: int | None) -> int:
    ref = load_reference(CACHE / "easysbc")
    with get_session() as session:
        ids = sample_resource_ids(session, ref, per_family=per_family)
        have = set(session.scalars(select(CardAttributes.resource_id)))
        todo = [i for i in ids if i not in have][:limit]
        assets = dict(session.execute(select(Card.resource_id, Card.asset_id)).all())
        client = make_client(futgg.BASE_URL, cache_dir=CACHE / "futgg")
        saved = 0
        try:
            for n, rid in enumerate(todo, 1):
                attrs = fetch_card_attributes(client, str(assets[rid]), rid)
                if attrs:
                    upsert_card_attributes(session, rid, attrs)
                    saved += 1
                if n % 50 == 0:
                    print(f"  {n}/{len(todo)}", flush=True)
        finally:
            client.close()
    print(f"muestra: {len(ids)} cartas, {len(todo)} por bajar, {saved} guardadas")
    return 0


def report() -> int:
    ref = load_reference(CACHE / "easysbc")
    with get_session() as session:
        for fam in FAMILIES:
            ds = build_dataset(session, ref, fam)
            if len(ds.y) < 15:
                print(f"{fam}: {len(ds.y)} cartas (insuficiente)")
                continue
            r = fit_family(ds)
            top = sorted(r.coef.items(), key=lambda kv: -kv[1])[:8]
            print(
                f"{fam}: n={r.n} R²={r.r2:.2f} corr CV={r.cv_corr:.2f} intercepto={r.intercept:.1f}"
            )
            print("   ", ", ".join(f"{k}={v:.3f}" for k, v in top))
    return 0


def fit() -> int:
    import json
    from datetime import date

    from fcsl_api.meta.fitted import WEIGHTS_FILE

    ref = load_reference(CACHE / "easysbc")
    with get_session() as session:
        roles = fit_all(session, ref)
    doc = {
        "generated": date.today().isoformat(),
        "note": "ajuste por regresión (ridge, coef >= 0); ver meta/calibration.py",
        "roles": roles,
    }
    WEIGHTS_FILE.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for name, r in roles.items():
        print(f"{name}: n={r['n']} R2={r['r2']} corrCV={r['cv_corr']}")
    print("escrito", WEIGHTS_FILE)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fcsl_api.meta")
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch-sample")
    f.add_argument("--per-family", type=int, default=70)
    f.add_argument("--limit", type=int, default=None)
    sub.add_parser("report")
    sub.add_parser("fit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    if args.command == "fetch-sample":
        return fetch_sample(args.per_family, args.limit)
    if args.command == "fit":
        return fit()
    return report()


if __name__ == "__main__":
    sys.exit(main())
