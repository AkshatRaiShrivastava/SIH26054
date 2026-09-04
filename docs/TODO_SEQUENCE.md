# Sequential TODOs — Digital Twin Project

This file lists all TODOs in a clear sequence with priority and short instructions.

1. Initialize database schema (P0)
   - Run: `python -m src.database.database` or `make train-model` which will call it.
   - Status: done

2. Extend `generate_telemetry.py` to export labeled runs for ML (P0)
   - Goal: Add CLI flag `--export-labels` to dump per-flight CSVs with `fault_label` and `rul`.
   - Why: Needed to create training datasets for anomaly and RUL models.
   - Owner: Person A
   - Status: not started

3. Add vibration processing module `src/utils/vibration.py` (P0)
   - Goal: Compute FFT band energies and RMS from windows of `vibration_g`.
   - Why: Vibration features are essential for mechanical-fault detection.
   - Owner: Person C
   - Status: completed

4. Add ML training script `Code/ml/train_baseline.py` (P0)
   - Goal: Train IsolationForest anomaly model and export to `Code/ml/models/`.
   - Status: completed

5. Add inference script `Code/ml/infer.py` (P0)
   - Goal: Score latest telemetry window and return `anomaly_score` JSON.
   - Status: completed

6. Integrate ML panel into `src/app/dashboard.py` (P0)
   - Goal: Display anomaly score and simple RUL placeholder.
   - Status: completed

7. Create model serving endpoint (FastAPI) (P1)
   - Goal: Provide `/infer` route for low-latency inference.
   - Owner: Person B
   - Status: not started

8. Implement state estimator (EKF/UKF) (P1)
   - Goal: Fuse RPM/temps/pressures with physics model to estimate latent states.
   - Status: not started

9. Implement CAN/ECU adapter `can_adapter.py` (P1)
   - Goal: Read SocketCAN frames or replay logs and normalize fields to DB schema.
   - Status: not started

10. Build RUL model (LSTM/Transformer) and training pipeline (P1)
    - Goal: Train regression model for remaining useful life using labeled synthetic runs.
    - Status: not started

11. Explainability & evaluation (P2)
    - Goal: Add SHAP summaries for anomaly alerts, evaluation metrics, and test harness.
    - Status: not started

12. Deployment & security (P2)
    - Goal: Add TLS, API keys, model signing, Dockerfiles, and deployment docs.
    - Status: not started

13. CI & reproducibility (P2)
    - Goal: Add GitHub Actions or CI job to run `make train-model` and smoke tests.
    - Status: not started

---

How to use this file:
- Follow tasks in order for fastest incremental value (P0 first).
- Update the `Status:` line as you complete tasks.
- If you want, I can convert this into GitHub Issues one-by-one.
