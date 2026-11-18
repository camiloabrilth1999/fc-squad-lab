from fcsl_api.ingest.futgg_detail import parse_card_attributes

# Formato real de FUT.GG: bloque contiguo de `attribute<Nombre>:<n>` (cada stat una
# vez), y más adelante `attributeStrength` sueltos de cartas relacionadas.
FIXTURE = (
    'foo.webp",eaId:84117827,x:1,'
    "attributeAcceleration:98,attributeSprintSpeed:97,attributeStrength:79,"
    "attributeFinishing:96,attributeBallControl:94,attributeDefensiveAwareness:17,"
    "attributeShortPassing:88,attributeGkDiving:13,"
    'next:"card",attributeStrength:88,attributeStrength:85'  # sueltos de otras cartas
)


def test_parse_extracts_main_block_and_maps_names():
    a = parse_card_attributes(FIXTURE, 84117827)
    assert a["acceleration"] == 98
    assert a["sprint_speed"] == 97
    assert a["finishing"] == 96
    assert a["ball_control"] == 94
    assert a["def_awareness"] == 17
    assert a["short_passing"] == 88


def test_parse_ignores_stray_later_attributes():
    a = parse_card_attributes(FIXTURE, 84117827)
    assert a["strength"] == 79  # el del bloque principal, no los 88/85 sueltos


def test_parse_skips_gk_stats():
    a = parse_card_attributes(FIXTURE, 84117827)
    assert "gk_diving" not in a and "diving" not in a  # los de portero no entran


def test_parse_wrong_card_returns_none():
    assert parse_card_attributes(FIXTURE, 99999999) is None  # el HTML no es de esa carta


def test_parse_no_attributes_returns_none():
    assert parse_card_attributes("eaId:84117827,sin:stats", 84117827) is None
