from fcsl_api.solver.models import Card


def make_card(**overrides) -> Card:
    data = {
        "card_id": "market:1",
        "resource_id": 1,
        "asset_id": 1,
        "name": "Jugador",
        "rating": 75,
        "positions": ["CM"],
        "league_id": 1,
        "nation_id": 1,
        "club_id": 1,
        "source": "market",
        "price": 1000,
    }
    data.update(overrides)
    return Card(**data)
