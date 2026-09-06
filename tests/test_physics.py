from physics.atmosphere import ambient_temperature_c, density_ratio
from physics.expected_values import expected_cht_c, expected_egt_c, expected_oil_pressure_kpa, expected_oil_temperature_c
from physics.deviation import deviation_pct


def test_density_ratio_positive():
    assert density_ratio(4200) > 0.0


def test_ambient_temp_formula():
    assert ambient_temperature_c(4200) < 15


def test_expected_cht_ref_case():
    value = expected_cht_c(4200, 4200, 18.0, 92.3)
    assert 150 < value < 180


def test_expected_egt_ref_case():
    value = expected_egt_c(4200, 18.0, 14.9)
    assert 700 < value < 800


def test_deviation_pct_logic():
    assert deviation_pct(110, 100) == 10.0
