import pytest

from fcsl_api.meta.roles import ROLES, get_role, role_for


def test_roles_seed_and_lookup():
    assert "adv_forward" in ROLES
    key_stats = ROLES["adv_forward"].key_stats
    for stat in ("acceleration", "finishing", "agility"):
        assert key_stats.get(stat, 0) > 0  # el rol de delantero pondera estos
    assert role_for("ST") in ROLES  # cada posición mapea a un rol existente
    assert role_for("CB") in ROLES
    with pytest.raises(KeyError):
        get_role("no_existe")  # rol desconocido: error claro


def test_every_role_has_well_formed_weights():
    for name, role in ROLES.items():
        assert role.key_stats, name  # no vacío
        assert all(w > 0 for w in role.key_stats.values()), name
