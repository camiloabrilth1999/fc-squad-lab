import pytest

from fcsl_api.objectives.parse import GroupMin, parse_objective

NBSP = "\xa0"


@pytest.mark.parametrize(
    ("text", "kind", "amount", "scope"),
    [
        ("Juega 3 partidos de Draft.", "play", 3, "draft"),
        ("Gana 100 partidos de Rivals.", "win", 100, "rivals"),
        (
            "Gana 25 partidos de Squad Battles en dificultad mínima Aficionado.",
            "win",
            25,
            "squad_battles",
        ),
        ("Gana 25 partidos de eventos en directo.", "win", 25, "live"),
        ("Juega 15 partidos de Rush.", "play", 15, "rush"),
        ("Juega 50 partidos cooperativos.", "play", 50, "coop"),
        (
            "Marca 500 goles en Squad Battles (o Rivals/Champions/Eventos en directo) en dificultad mínima Aficionado.",
            "goals",
            500,
            "online",
        ),
        (
            "Asiste en 500 goles en Squad Battles (o Rivals/Champions/Eventos en directo) en dificultad mínima Aficionado.",
            "assists",
            500,
            "online",
        ),
        (
            "Marca 10 goles en cualquier modo de FUT con 1 futbolista de Francia.",
            "goals",
            10,
            "any",
        ),
        (
            "Gana 3 partidos en cualquier modo de juego FUT con la equipación de evolución Ultimate Scream - Fase 1 equipada.",
            "win",
            3,
            "any",
        ),
        ("Gana 14 partidos en la Liga HOF: Desatado.", "win", 14, "event:liga hof: desatado"),
        (
            "Juega 20 partidos en el torneo eliminatorio diario de la Temporada 2.",
            "play",
            20,
            "event:torneo eliminatorio diario de la temporada 2",
        ),
        (
            "Marca 15 goles en el torneo eliminatorio diario de la Temporada 2.",
            "goals",
            15,
            "event:torneo eliminatorio diario de la temporada 2",
        ),
    ],
)
def test_parses_the_common_objective_patterns(
    text: str, kind: str, amount: int, scope: str
) -> None:
    t = parse_objective(text)
    assert t.plannable, t.reason
    assert (t.kind, t.amount, t.scope) == (kind, amount, scope)


def test_numbers_with_non_breaking_spaces() -> None:
    assert parse_objective(f"Gana{NBSP}50 partidos de Rivals.").amount == 50
    assert parse_objective("Marca 1 000 goles en cualquier modo de FUT.").amount == 1000


def test_goal_matches_and_multi_goal_in_one_match() -> None:
    t = parse_objective(
        "Marca al menos 1 gol en 50 partidos distintos en el torneo eliminatorio diario de la Temporada 2."
    )
    assert (t.kind, t.amount) == ("goal_matches", 50)
    t = parse_objective(
        "Marca al menos 2 goles en 1 partido con mín. 1 futbolista de la MLS en tu once inicial en el evento Aficionado del Circuito de Legado FC."
    )
    assert (t.kind, t.amount, t.per_match) == ("multi_goal", 1, 2)
    assert t.groups == (GroupMin("league", "MLS", 1),)


def test_squad_constraints_by_league_nation_and_club() -> None:
    t = parse_objective(
        "Gana 2 partidos con mín. 3 futbolistas de la Premier League en tu once inicial en el evento Profesional del Circuito de Legado FC."
    )
    assert t.groups == (GroupMin("league", "Premier League", 3),)
    t = parse_objective(
        "Marca al menos 1 gol en 3 partidos distintos con mín. 1 artículo de futbolista del Real Madrid (LALIGA) en tu once inicial en el evento Clase mundial del Circuito de Legado FC."
    )
    assert t.groups == (GroupMin("club", "Real Madrid (LALIGA)", 1),)
    t = parse_objective(
        "Juega 3 partidos en cualquier modo de Football Ultimate Team con al menos 2 futbolistas de EE. UU. en tu once inicial."
    )
    assert t.groups == (GroupMin("nation", "EE. UU.", 2),)
    t = parse_objective(
        "Juega 2 partidos con mín. 1 futbolista de Italia en tu once inicial en Squad Battles (o Rivals/Champions/Eventos en directo/Rush) en dificultad mínima Aficionado."
    )
    assert t.groups == (GroupMin("nation", "Italia", 1),)
    assert t.scope == "online"


def test_cosmetic_requirement_is_noted_but_still_plannable() -> None:
    t = parse_objective(
        "Juega 1 partido en cualquier modo de FUT con el Tifo de Movember equipado."
    )
    assert t.plannable and any("cosmético" in n for n in t.notes)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("Completa 250 grupos de desafío de creación de plantillas.", "SBC"),
        ("Pon a 500 futbolistas en el Mercado de transferibles.", "Mercado"),
        (
            "Compra 500 futbolistas en el Mercado de transferibles con la opción Comprar ya.",
            "Mercado",
        ),
        ("Consigue la evaluación S en el conjunto de la galería de Ultimate Scream.", "Galería"),
        (
            "Mira el clasificatorio global de FC Pro Open durante al menos 60 minutos.",
            "retransmisión",
        ),
        ("Gana 35 000 puntos al completar bonificaciones de Rush.", "Rush"),
        (
            "Gana 50 partidos en cualquier modo de FUT con una plantilla inicial de jugadores de primera adquisición.",
            "primera adquisición",
        ),
        ("Asiste 50 veces con centros en cualquier modo de FUT.", "jugada concreta"),
        ("Marca 50 goles de tiro libre directo en cualquier modo de FUT.", "jugada concreta"),
        (
            "Completa el objetivo del evento Clase mundial del Circuito de Legado FC.",
            "otros objetivos",
        ),
        ("Haz algo rarísimo.", "no se reconoce"),
    ],
)
def test_unplannable_objectives_say_why(text: str, reason: str) -> None:
    t = parse_objective(text)
    assert not t.plannable
    assert reason.lower() in (t.reason or "").lower()


def test_empty_description_is_not_plannable() -> None:
    assert not parse_objective(None).plannable
