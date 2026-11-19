"""Recompensas de los objetivos de EA, descritas de forma legible."""

from typing import Any

_KNOWN = {
    "graduated_access_transfer_market_entry": "Acceso al mercado de transferencias",
}


def _n(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def describe_award(
    award: dict[str, Any], names: dict[int, str], pack_names: dict[int, str] | None = None
) -> dict[str, Any]:
    """{type, label, count} de una recompensa.

    `names` mapea resource_id → nombre de jugador y `pack_names` id de sobre → nombre.
    """
    kind = str(award.get("type", ""))
    value = int(award.get("value") or 0)
    count = int(award.get("count") or 1)
    amount = value * count
    if kind == "coin":
        label = f"{_n(amount)} monedas"
    elif kind == "xp":
        label = f"+{_n(amount)} XP"
    elif kind == "pack":
        pack = (pack_names or {}).get(value) or f"Sobre #{value}"
        label = f"{count}× {pack}" if count > 1 else pack
    elif kind == "item":
        item = award.get("item") or {}
        rid = item.get("resource_id", value)
        name = names.get(rid) or f"Jugador #{rid}"
        rating = item.get("rating")
        label = f"{name} ({rating})" if rating else name
        if count > 1:
            label = f"{count}× {label}"
    elif kind.startswith("event_token"):
        label = f"Ficha de evento ×{amount}"
    elif kind in _KNOWN:
        label = _KNOWN[kind]
    else:
        label = f"{kind} ×{amount}"
    return {"type": kind, "label": label, "count": count}
