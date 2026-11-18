"""Selección de las cartas que entran al modelo CP-SAT y poda exacta del mercado."""

from collections import defaultdict
from collections.abc import Callable, Hashable
from typing import Literal

from .models import Card, Position, Requirement, RequirementKind

PoolKind = Literal["club", "both", "market"]


def _passes_player_rating(card: Card, reqs: list[Requirement]) -> bool:
    for req in reqs:
        if req.kind != RequirementKind.PLAYER_RATING:
            continue
        if req.op == "min" and card.rating < req.value:
            return False
        if req.op == "max" and card.rating > req.value:
            return False
        if req.op == "exact" and card.rating != req.value:
            return False
    return True


def build_pool(
    cards: list[Card],
    pool: PoolKind,
    slots: list[Position],
    requirements: list[Requirement],
    include_ids: list[str],
    exclude_ids: list[str],
) -> list[Card]:
    """Cartas candidatas para el modelo, en el orden de entrada.

    1. Filtra por origen (`pool`); 2. quita excluidas y mercado sin precio;
    3. quita las que violan PLAYER_RATING; 4. poda el mercado por grupos de cartas
    intercambiables (ver `_prune_market`). Las propias y las de `include_ids` nunca
    se podan. No se descarta ninguna carta por posición: cualquier carta puede ir
    en cualquier hueco (fuera de posición), la posición solo afecta a la química.
    """
    sources = {"club": {"club"}, "market": {"market"}, "both": {"club", "market"}}[pool]
    include, exclude = set(include_ids), set(exclude_ids)
    candidates = [
        card
        for card in cards
        if card.source in sources
        and card.card_id not in exclude
        and not (card.source == "market" and card.price is None)
        and _passes_player_rating(card, requirements)
    ]
    keep = _prune_market(candidates, slots, requirements, include)
    return [card for card in candidates if card.card_id in keep]


_CHEM_KINDS = {RequirementKind.TEAM_CHEMISTRY, RequirementKind.PLAYER_CHEMISTRY}
_FAMILY_KINDS = {
    "league": {
        RequirementKind.LEAGUE_PLAYERS,
        RequirementKind.DISTINCT_LEAGUES,
        RequirementKind.SAME_LEAGUE,
    },
    "nation": {
        RequirementKind.NATION_PLAYERS,
        RequirementKind.DISTINCT_NATIONS,
        RequirementKind.SAME_NATION,
    },
    "club": {
        RequirementKind.CLUB_PLAYERS,
        RequirementKind.DISTINCT_CLUBS,
        RequirementKind.SAME_CLUB,
    },
}
# Tipos cuyo efecto sobre la carta está modelado abajo; ante uno desconocido la
# clave usa todos los atributos (poda conservadora).
_KNOWN_KINDS = (
    _CHEM_KINDS
    | set().union(*_FAMILY_KINDS.values())
    | {
        RequirementKind.TEAM_RATING,
        RequirementKind.PLAYER_RATING,
        RequirementKind.LEVEL_PLAYERS,
        RequirementKind.RARE_PLAYERS,
        RequirementKind.TAG_PLAYERS,
        RequirementKind.RATING_PLAYERS,
    }
)


def _class_key(requirements: list[Requirement]) -> Callable[[Card], Hashable]:
    """Clave de equivalencia según los requisitos: dos cartas de mercado con la
    misma clave se comportan igual en todo requisito y en el objetivo, salvo por
    rating, posiciones y precio (que se comparan por dominancia).

    Solo entran los atributos que algún requisito mira: la química usa club, liga,
    nación e icono/héroe; *_PLAYERS/DISTINCT_*/SAME_* su familia; LEVEL el nivel;
    RARE la rareza; TAG las etiquetas pedidas. Las marcas que afectan al objetivo
    (intransferible, duplicada, almacén) siempre entran.
    """
    kinds = {req.kind for req in requirements}
    full = not kinds <= _KNOWN_KINDS
    chem = full or bool(kinds & _CHEM_KINDS)
    fams = {f for f, ks in _FAMILY_KINDS.items() if full or chem or kinds & ks}
    level = full or RequirementKind.LEVEL_PLAYERS in kinds
    rare = full or RequirementKind.RARE_PLAYERS in kinds
    tags: set[str] | None = None  # None = todas
    if not full:
        tags = {t for r in requirements if r.kind == RequirementKind.TAG_PLAYERS for t in r.tags}

    def key(card: Card) -> Hashable:
        return (
            card.league_id if "league" in fams else None,
            card.nation_id if "nation" in fams else None,
            card.club_id if "club" in fams else None,
            (card.is_icon, card.is_hero) if chem else None,
            card.level if level else None,
            card.rare if rare else None,
            frozenset(card.rarity_tags if tags is None else tags & set(card.rarity_tags)),
            card.untradeable,
            card.duplicate,
            card.in_sbc_storage,
        )

    return key


def _rating_mode(requirements: list[Requirement]) -> str:
    """'ignore': el rating no importa; 'higher': más rating nunca empeora (solo
    TEAM_RATING mínimos, la media es no decreciente en cada rating); 'exact': hay
    TEAM_RATING max/exact o requisitos desconocidos.
    """
    kinds = {req.kind for req in requirements}
    if not kinds <= _KNOWN_KINDS:
        return "exact"
    if RequirementKind.RATING_PLAYERS in kinds:
        # Una ventana de GRL por carta: subir el rating puede sacar a una carta de
        # la ventana (máx) o meterla (mín), así que no es monótono; poda por rating
        # exacto (dos cartas solo se dominan con el mismo rating).
        return "exact"
    team = [r for r in requirements if r.kind == RequirementKind.TEAM_RATING]
    if not team:
        return "ignore"  # PLAYER_RATING ya se filtró; LEVEL va en la clave
    if all(r.op == "min" for r in team):
        return "higher"
    return "exact"


def _prune_market(
    cards: list[Card],
    slots: list[Position],
    requirements: list[Requirement],
    include: set[str],
) -> set[str]:
    """card_ids que sobreviven: todas las propias e incluidas, más las de mercado
    no dominadas.

    d domina a c (ambas de mercado y con la misma `_class_key`) si d juega en
    todos los huecos que c (posiciones∩huecos ⊇), su rating no es peor según
    `_rating_mode`, cuesta ≤ y precede a c en el orden total
    (precio, −rating, −nº posiciones, card_id). Cambiar c por d en su hueco
    mantiene todos los requisitos y no empeora ningún objetivo (todos son
    monótonos en el precio para cartas de mercado con las mismas marcas).

    Se quita c (de mercado, no incluida) si, en toda solución que use c, alguna
    dominadora d queda libre (ni usada ni bloqueada por asset):
    - R0: una dominadora tiene el mismo asset que c (c la bloquea a ella sola);
    - R1: las dominadoras tienen ≥ n assets distintos de c (las otras n − 1
      cartas de la solución excluyen como mucho un asset cada una).
    Ambas reglas se basan solo en assets, así que siguen siendo válidas aunque las
    cartas puedan jugar fuera de posición (el intercambio c→d mantiene la química:
    d juega en el mismo hueco que c, en posición o fuera de ella, igual que c).
    Repitiendo el cambio (el orden total es estricto) se llega a una solución
    igual o mejor que solo usa cartas conservadas: la poda es exacta.
    """
    n = len(slots)
    slot_set = frozenset(slots)
    key = _class_key(requirements)
    mode = _rating_mode(requirements)
    keep = {card.card_id for card in cards if card.source == "club" or card.card_id in include}

    classes: dict[Hashable, list[Card]] = defaultdict(list)
    for card in cards:
        if card.source == "market":
            classes[key(card)].append(card)

    def rank(card: Card) -> tuple:
        return (card.price, -card.rating, -len(slot_set & set(card.positions)), card.card_id)

    for members in classes.values():
        # buckets[(posiciones∩huecos, rating)] = cartas en orden total creciente
        buckets: dict[tuple[frozenset[str], int], list[Card]] = defaultdict(list)
        for card in sorted(members, key=rank):
            rating = card.rating if mode != "ignore" else 0
            buckets[frozenset(slot_set & set(card.positions)), rating].append(card)
        for card in members:
            if card.card_id in keep:
                continue
            if not _dominated(card, buckets, slot_set, n, mode, rank):
                keep.add(card.card_id)
    return keep


def _dominated(
    card: Card,
    buckets: dict[tuple[frozenset[str], int], list[Card]],
    slot_set: frozenset[str],
    n: int,
    mode: str,
    rank: Callable[[Card], tuple],
) -> bool:
    playable = frozenset(slot_set & set(card.positions))
    rating = card.rating if mode != "ignore" else 0
    my_rank = rank(card)
    assets: set[int] = set()
    for (pos_set, r), bucket in buckets.items():
        if not pos_set >= playable:
            continue
        if mode == "higher" and r < rating:
            continue
        if mode != "higher" and r != rating:
            continue
        for other in bucket:
            if rank(other) >= my_rank:
                break  # el bucket va en orden total: el resto no precede a `card`
            if other.asset_id == card.asset_id:
                return True  # R0
            assets.add(other.asset_id)
            if len(assets) >= n:
                return True  # R1
    return False
