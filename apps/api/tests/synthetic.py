"""Generador determinista de cartas de mercado sintéticas para pruebas de rendimiento."""

import random

from fcsl_api.solver.models import Card, Position

FORMATION_433: list[Position] = [
    "GK",
    "LB",
    "CB",
    "CB",
    "RB",
    "CM",
    "CM",
    "CM",
    "LW",
    "ST",
    "RW",
]

_POSITIONS: list[Position] = [
    "GK",
    "LB",
    "CB",
    "RB",
    "LWB",
    "RWB",
    "CDM",
    "CM",
    "CAM",
    "LM",
    "RM",
    "LW",
    "RW",
    "CF",
    "ST",
]
# Posiciones alternativas plausibles para cada preferida.
_ALT: dict[str, list[str]] = {
    "GK": [],
    "LB": ["LWB", "LM"],
    "CB": ["CDM", "RB", "LB"],
    "RB": ["RWB", "RM"],
    "LWB": ["LB", "LM"],
    "RWB": ["RB", "RM"],
    "CDM": ["CM", "CB"],
    "CM": ["CDM", "CAM"],
    "CAM": ["CM", "CF"],
    "LM": ["LW", "LB"],
    "RM": ["RW", "RB"],
    "LW": ["LM", "ST"],
    "RW": ["RM", "ST"],
    "CF": ["ST", "CAM"],
    "ST": ["CF", "LW", "RW"],
}
_RATINGS = list(range(75, 91))
_PRICE_BY_RATING = {
    75: 350,
    76: 450,
    77: 550,
    78: 700,
    79: 850,
    80: 1100,
    81: 1500,
    82: 2300,
    83: 4000,
    84: 7000,
    85: 11000,
    86: 16000,
    87: 24000,
    88: 35000,
    89: 50000,
    90: 75000,
}

N_LEAGUES = 6
CLUBS_PER_LEAGUE = 12
N_NATIONS = 18


def market_cards(n: int, seed: int) -> list[Card]:
    rng = random.Random(seed)
    rating_weights = [1.0 / (1.25 ** (r - 75)) for r in _RATINGS]
    nation_weights = [1.0 / (k + 1) for k in range(N_NATIONS)]
    cards: list[Card] = []
    for i in range(1, n + 1):
        league = rng.randrange(N_LEAGUES) + 1
        club = league * 100 + rng.randrange(CLUBS_PER_LEAGUE)
        # La mitad juega con la nación "local" de su liga.
        if rng.random() < 0.5:
            nation = league
        else:
            nation = rng.choices(range(1, N_NATIONS + 1), weights=nation_weights)[0]
        rating = rng.choices(_RATINGS, weights=rating_weights)[0]
        primary = rng.choice(_POSITIONS)
        alts = _ALT[primary]
        positions = [primary] + rng.sample(alts, k=min(len(alts), rng.randrange(3)))
        price = _PRICE_BY_RATING[rating] * rng.uniform(0.85, 1.6)
        price = int(round(price / 50) * 50)
        cards.append(
            Card(
                card_id=f"market:{i}",
                resource_id=i,
                asset_id=i,
                name=f"S{i}",
                rating=rating,
                positions=positions,
                league_id=league,
                nation_id=nation,
                club_id=club,
                rare=rng.random() < 0.7,
                source="market",
                price=price,
            )
        )
    return cards
