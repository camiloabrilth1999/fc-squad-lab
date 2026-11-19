import numpy as np

from fcsl_api.meta.calibration import Dataset, family_of, fit_family
from fcsl_api.meta.fitted import FEATURE_NAMES


def test_fit_recovers_known_linear_weights():
    rng = np.random.default_rng(1)
    n, k = 200, len(FEATURE_NAMES)
    X = rng.uniform(40, 95, size=(n, k))
    i_fin, i_acc = FEATURE_NAMES.index("finishing"), FEATURE_NAMES.index("acceleration")
    y = -20 + 0.6 * X[:, i_fin] + 0.3 * X[:, i_acc]
    r = fit_family(Dataset(list(range(n)), X, y), "adv_forward", ridge=0.01)
    assert r.cv_corr > 0.99
    assert abs(r.coef["finishing"] - 0.6) < 0.05
    assert abs(r.coef["acceleration"] - 0.3) < 0.05
    assert abs(r.intercept - (-20)) < 3


def test_fit_coefficients_are_never_negative():
    rng = np.random.default_rng(2)
    X = rng.uniform(40, 95, size=(120, len(FEATURE_NAMES)))
    y = 30 + 0.5 * X[:, 0] - 0.4 * X[:, 1]  # una dependencia negativa: se descarta
    r = fit_family(Dataset(list(range(120)), X, y), "adv_forward", ridge=0.01)
    assert all(v >= 0 for v in r.coef.values())


def test_family_of_positions():
    assert family_of("ST") == "adv_forward"
    assert family_of("LM") == "winger"
    assert family_of("CB") == "defender"
    assert family_of("GK") == "goalkeeper"
