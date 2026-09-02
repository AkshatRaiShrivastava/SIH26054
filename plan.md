# Simple Plan for Digital Twin Project

This file lists what to do next and how to do it in simple English.

## Goal

Build a clear, working Digital Twin prototype that shows engine health, detects faults,
and lets us replay missions. Keep it modular so we can add ML and CAN input later.

## Priority (Do these first)

- P0: ML baseline + dataset
  - What: Create a simple anomaly detector and a small RUL model using synthetic data.
  - How: Extend `generate_telemetry.py` to export labeled runs (normal +_fault). Add a
    training script that loads these runs, trains a simple autoencoder (for anomalies)
    and a small LSTM (for RUL), and saves the models as ONNX or pickle.

- P0: Dashboard integration
  - What: Show anomaly score and RUL on the Streamlit dashboard.
  - How: Add a side panel in the dashboard that polls the latest evaluation rows from the
    database and displays `anomaly_score` and `predicted_rul` with color-coded warnings.

- P0: Vibration processing
  - What: Add a module to compute FFT/spectrogram from raw accelerometer windows.
  - How: Create `utils/vibration.py` that computes windowed FFT and extracts features
    (band energies, RMS). Store features to `telemetry` or a separate `vibration` table.

## Important (After P0)

- P1: CAN / ECU input adapter
  - What: Read real-time engine data from SocketCAN or `python-can` and feed the pipeline.
  - How: Implement `can_adapter.py` with mapping from CAN IDs to named signals. Provide a
    mock mode that replays logged CAN traces for testing.

- P1: State estimator (EKF/UKF)
  - What: Fuse sensors and physics model to estimate latent states (combustion efficiency).
  - How: Implement a small EKF module that uses measured RPM, CHT, oil pressure and
    predicts expected signals; write tests with synthetic data.

- P1: Model serving & edge runtime
  - What: Run models on a small local server (Flask/FastAPI) or as a lightweight process.
  - How: Create an inference route that accepts recent telemetry, returns anomaly score and RUL.

## Nice-to-have (Later)

- P2: Physics-informed ML (use physics model + ML for residual learning)
- P2: Explainability (SHAP summaries for alerts)
- P2: Federated learning or edge aggregation
- P2: Secure telemetry (TLS, authentication) and deployment docs

## How to start (first day checklist)

1. Run the generator to create training data:

```bash
python Code/scripts/quickstart.py
```

2. Add a small training script `ml/train_baseline.py` that reads exported runs and trains.

3. Add a dashboard panel in `Code/src/app/dashboard.py` to display model outputs.

4. Make one end-to-end smoke test: generate → evaluate → model predict → dashboard shows.

## Who does what (suggested split)

- Person A: Extend `generate_telemetry.py` to export labeled fault/RUL datasets and create training data.
- Person B: Implement the ML baseline (`ml/train_baseline.py`, `ml/infer.py`) and ONNX export.
- Person C: Dashboard changes and vibration processing module.

## Notes

- Keep changes small and test after each step.
- Save models and dataset versions (timestamped) for reproducibility.






## Fault Prediction

- What is fault prediction?

Now suppose your system sees:

Fuel flow ↑
EGT ↑
RPM unstable
Injection timing abnormal

It might predict:

Possible injector problem

Similarly:

Oil pressure ↓
Oil temperature ↑

→ Possible lubrication problem

Or:

CHT ↑
EGT ↑
Ambient temperature ↑

→ Possible overheating trend