from rul.predict import predict_rul


def test_rul_predict_healthy_input():
    result = predict_rul([], {"health_index": 95.0, "oil_pressure_deviation_pct": 1.0, "vibration_deviation_pct": 0.5, "cht_deviation_pct": 0.2})
    assert result['predicted_rul_minutes'] >= 0
    assert result['confidence_band_minutes'] >= 0
