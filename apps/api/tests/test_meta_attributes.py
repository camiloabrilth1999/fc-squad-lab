from fcsl_api.meta.attributes import PlayerAttributes


def test_player_attributes_defaults_missing_to_zero():
    attrs = PlayerAttributes(agility=88, finishing=90, accelerate="EXPLOSIVE")
    assert attrs.get("agility") == 88
    assert attrs.get("finishing") == 90
    assert attrs.get("vision") == 0  # no provisto: cuenta como 0
    assert attrs.get("no_es_un_stat") == 0  # nombre desconocido: 0, sin romper
    assert attrs.accelerate == "EXPLOSIVE"
    assert attrs.play_styles == [] and attrs.play_styles_plus == []
