# Digital Twin — Architecture & Data Flow

This document describes the high-level architecture and data flow for the Digital Twin project.
It is written in simple language and includes a data-flow diagram you can copy into eraser.io or other diagram tools.

## Goal

Build a modular digital twin that ingests engine telemetry (real or simulated),
applies physics evaluation, runs ML-based analytics (anomaly detection and RUL),
and exposes results to a dashboard and maintenance systems.

## Components

- Edge / Data Sources
  - Real: CAN/SocketCAN, ECU/FADEC, accelerometer traces
  - Simulated: `generate_telemetry.py` (seeded flight generator)
- Ingest / Adapters
  - `can_adapter.py` (SocketCAN reader or replay mode)
  - Telemetry writer: writes normalized rows to SQLite (`data/digital_twin.db`)
- Database
  - SQLite DB with `flights`, `telemetry`, `evaluations`, `flight_condition`, `corrosion_tracking`
- Physics Layer
  - `physics_layer.py` / `PhysicsEvaluator`: computes expected values, deviations, debounced statuses, icing, density altitude
- Signal Processing
  - `src/utils/vibration.py`: FFT/spectrogram features for vibration analysis
- ML Layer
  - Training: `Code/ml/train_baseline.py` (creates anomaly model)
  - Inference: `Code/ml/infer.py` (scores latest window per flight)
  - Optional model server (FastAPI) for edge/cloud inference
- Dashboard / HMI
  - Streamlit app: `src/app/dashboard.py` — live view, history, maintenance panel
- Model & Artifacts Storage
  - `Code/ml/models/` for pickled/ONNX models
- Ops & Security
  - TLS/auth for remote telemetry, model versioning, deployment docs

## Data Flow (textual)

1. Source (CAN or simulator) emits telemetry packets.
2. Adapter normalizes packets and writes rows to `telemetry` table.
3. Physics Layer polls `telemetry`, computes `evaluations` and `flight_condition`, writes to DB.
4. Signal processing (vibration) consumes raw windows and writes features or a `vibration` table.
5. ML Inference component reads recent windows from `telemetry` (or features), loads model, returns `anomaly_score` and optionally `predicted_rul`.
6. Dashboard polls DB and ML endpoint to render health, anomaly alerts, RUL, and trend charts.
7. Operators can replay flights by replaying `telemetry` rows; ML and physics operate over historical data.

## Mermaid data-flow diagram (paste into a renderer like eraser.io or Mermaid live)

```mermaid
flowchart TD
  subgraph Edge
    A[CAN / ECU / Sensors]
    B[Simulator: generate_telemetry.py]
  end

  subgraph Ingest
    C[can_adapter.py / ingest writer]
    D[SQLite DB (telemetry, flights, evaluations)]
  end

  subgraph Processing
    E[Physics Layer (PhysicsEvaluator)]
    F[Vibration Processor]
    G[ML Inference / Model Server]
  end

  subgraph UI
    H[Streamlit Dashboard]
    I[Maintenance / Reports]
  end

  A --> C --> D
  B --> C --> D
  D --> E --> D
  D --> F --> D
  D --> G --> D
  G --> H
  E --> H
  D --> H
  H --> I

  classDef edge fill:#f9f,stroke:#333,stroke-width:1px;
  class A,B edge;
  classDef db fill:#ffd,stroke:#333;
  class D db;
``` 

## Sequence of operations (runtime)

1. Start data source (real CAN stream or run `generate_telemetry.py`).
2. Adapter writes normalized telemetry rows to DB.
3. Physics layer runs continuously (live) or in replay mode:
   - For each new packet: compute expected values, deviations, raw_status.
   - Apply debounce logic and write debounced `status` into `evaluations`.
   - Compute `flight_condition` (subsystem health rollup).
4. Vibration module computes features from recent windows and writes them for ML.
5. ML inference scores recent windows and writes anomaly_score (or model server provides on request).
6. Dashboard polls DB + ML and renders live health, anomaly alerts, and RUL.

## Deployment options

- Edge-only: Run generator + physics + lightweight ML on a local rugged computer on the ground station.
- Edge compute + Cloud: Edge does ingest & preprocessing; cloud runs heavy model training and fleet-level analytics.
- Fleet/Enterprise: PostgreSQL or time-series DB replace SQLite for higher throughput.

## Security & Compliance (brief)

- Authenticate sensors/adapters (API keys, TLS).
- Sign telemetry packets if operating in contested environments.
- Model file integrity: sign model artifacts and track versions.

---

If you want, I can also export the Mermaid diagram as an image or push a visual to eraser.io (requires your API key). Which would you prefer? 
