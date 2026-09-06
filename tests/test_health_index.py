from health_index.composite import health_index_score


def test_health_index_bounds():
    value = health_index_score([5.0, 3.0, 1.0], 0.02)
    assert 0 <= value <= 100
