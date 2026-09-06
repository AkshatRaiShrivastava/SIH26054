from rules.fault_signatures import classify_fault


def test_fault_signature_for_lubrication():
    result = classify_fault({
        'cht_deviation_pct': 5,
        'egt_deviation_pct': 6,
        'oil_pressure_deviation_pct': 15,
        'oil_temp_deviation_pct': 9,
        'vibration_deviation_pct': 8,
    })
    assert result['fault_category'] == 'lubrication_problem'
