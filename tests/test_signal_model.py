from simulator.signal_model import simulate_tick


def test_signal_model_generates_values():
    sample = simulate_tick(120.0, {}, 'normal')
    assert sample['rpm'] > 0
    assert sample['cht_c'] > 0
    assert sample['oil_pressure_kpa'] > 0
