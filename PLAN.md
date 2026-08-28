SIH 2026 — Problem
Statement 54 (DRDO)
AI-Enabled Real-Time Digital Twin
System for Health Monitoring, Fault
Prediction and Mission Reliability
Enhancement of Aero Piston
Engines used in MALE UAVs
Category: Software | Theme: Robotics and Drones |
Organization: DRDO
1. Problem Summary
MALE (Medium Altitude Long Endurance) UAVs rely
on piston engines for long-duration ISR,
communication relay, maritime surveillance, and
strategic defence missions. Engine failure in flight risks
mission abort, asset loss, or unsafe recovery. Current
UAV engine monitoring is threshold-based and
reactive — it only flags failure after it's already
happening, with no ability to predict Remaining Useful

Life (RUL), track degradation trends, or simulate
engine behavior under different
missions/environments.
We are building: a software Digital Twin system — a
live virtual model of the engine, continuously synced
with sensor data — that monitors health, predicts
faults before they occur, and supports pre-flight
simulation and post-flight replay.
2. Tech Stack
| Layer | Technology | Why |
| ----- | ---------- | --- |
Backbone
| Core |     | across data, |
| ---- | --- | ------------ |
Python
| language |     | ML, and |
| -------- | --- | ------- |
backend
Fast, modern,
well-
| Backend / |     | documented; |
| --------- | --- | ----------- |
FastAPI
| API |     | serves twin |
| --- | --- | ----------- |
data to
dashboard
| Real-time  | MQTT ( paho- | Standard    |
| ---------- | ------------ | ----------- |
| telemetry  | mqtt ) or    | lightweight |
| simulation | WebSockets   | protocol to |

| Layer | Technology | Why |
| ----- | ---------- | --- |
simulate live
sensor
streaming
Structuring and
| Data |     | generating |
| ---- | --- | ---------- |
Pandas, NumPy
| handling |     | synthetic |
| -------- | --- | --------- |
sensor data
Well-
documented,
|     | Scikit-learn | proven for |
| --- | ------------ | ---------- |
Anomaly
|     | (Isolation Forest / | "detect |
| --- | ------------------- | ------- |
detection
|     | One-Class SVM) | abnormal |
| --- | -------------- | -------- |
pattern in time-
series" tasks
|            | Scikit-learn      | Standard       |
| ---------- | ----------------- | -------------- |
| RUL /      | regression,       | approach for   |
| trend      | optionally LSTM   | time-series    |
| prediction | (TensorFlow/Keras | degradation    |
|            | or PyTorch)       | prediction     |
| Physics-   | Rule-based Python | e.g., expected |
| informed   | models            | oil temp as a  |
| layer      |                   | function of    |
RPM + ambient
temp — hybrid
thermodynamic
+ data-driven,

Layer Technology Why
per DRDO's
"Desired
Innovation
Areas"
Stores
SQLite (prototype)
historical
Database → PostgreSQL
mission data
(scalable)
for replay
Streamlit (fast
Real-time
path) or React +
Dashboard engine health
Chart.js/Recharts
visualization
(polished path)
Version Team
Git + GitHub
control collaboration
Decision point for team: Streamlit = faster to build,
Python-only, good enough for demo. React = more
polished UI, needs a frontend-comfortable teammate.
Pick based on team skill distribution.
3. Phase-Wise Plan (MVP → Final
Product)
Phase 0 — Foundation (Week 1)

Finalize architecture (see diagram below)
Set up Git repo, environment, shared folder
structure
Assign roles: data/simulation, ML/anomaly
detection, backend, dashboard, research/docs
Define the exact sensor parameter list + realistic
value ranges (RPM, CHT, EGT, oil pressure/temp,
fuel flow, vibration, battery/alternator health,
injection timing)
Phase 1 — MVP: Synthetic Data + Basic
Monitoring (Weeks 2-3)
Build synthetic sensor data generator (healthy
engine + injected degradation patterns)
Store data in SQLite
Basic FastAPI endpoints to serve live/simulated
sensor readings
Barebones dashboard (Streamlit) showing raw
parameter values in real time
Deliverable: data pipeline works end-to-end,
nothing intelligent yet
Phase 2 — Digital Twin Core + Health
Monitoring (Weeks 4-5)
Build the "expected behavior" virtual model
(physics-informed rules: e.g. expected CHT/oil

temp ranges per RPM/altitude/environment)
Compare live vs. expected → generate health
indices per subsystem
Dashboard shows real-time health status, not just
raw values
Phase 3 — Fault Detection & Predictive
Analytics (Weeks 6-7)
Train anomaly detection model (Isolation Forest)
on synthetic data
Detect: misfire conditions, injector abnormalities,
lubrication issues, sensor drift, combustion
instability, overheating trends, abnormal vibration
Add fault alerts to dashboard
Phase 4 — AI/ML Layer: RUL + Trend
Analysis (Weeks 8-9)
Build RUL estimation model (regression or LSTM)
on synthetic degradation sequences
Trend analysis visualization (degradation curves
over time)
Predictive maintenance recommendations (rule-
based output tied to RUL/health index thresholds)
Phase 5 — Simulation & Replay Capability
(Week 10)

Mission-profile simulator: generate engine
behavior under high-altitude, endurance, hot-
weather, rapid-throttle scenarios
Historical mission replay feature (pull stored
mission data, replay on dashboard)
Environmental condition simulation tied to India-
specific climate zones (border states, IOR
maritime)
Phase 6 — Dashboard Polish +
Documentation (Weeks 11-12)
Finalize dashboard: real-time health status, fault
alerts, efficiency trends, maintenance advisory,
mission-wise health reports
Technical documentation + deployment roadmap
Rehearse live demo end-to-end, prep for judge
Q&A
Note: Timeline assumes ~10-12 weeks between
shortlisting and Grand Finale — compress
proportionally if actual window is shorter. Phases 1-2
are the non-negotiable MVP if time runs short.
4. System Architecture
flowchart TD
A[Engine Sensors + FADEC] -->|CAN bus /

SocketCAN| B[Real-Time Data Ingestion
Layer]
B --> C[Digital Twin Core Framework]
C --> D[Physics-Informed
Model<br/>expected behavior]
C --> E[Live Sensor Data<br/>actual
behavior]
D --> F{Compare: Expected vs Actual}
E --> F
F --> G[Health Monitoring
System<br/>RPM, CHT, EGT, Oil P/T, Fuel
Flow,<br/>Vibration, Battery, Injection
Timing]
F --> H[Fault Detection & Predictive
Analytics<br/>Anomaly Detection - Scikit-
learn]
H --> I[AI/ML Layer<br/>RUL Estimation,
Trend Analysis]
G --> J[Simulation & Replay
Module<br/>Mission Profiles, Historical
Replay]
I --> J
J --> K[Visualization
Dashboard<br/>Streamlit / React]
K --> L[UAV Operators]
K --> M[Propulsion Engineers]
K --> N[Maintenance Teams]
5. Role Mapping

Maps to
Role Responsibility
phase
Overall design,
Lead / All
domain research,
Architecture phases
pitch narrative
Synthetic sensor +
Data / Phase 1,
mission data
Simulation 5
generation
Anomaly detection, Phase 3,
ML Engineer
RUL model 4
FastAPI, database, Phase 1,
Backend
data pipeline 2
Frontend Phase 1,
Dashboard
visualization 6
Feasibility,
Research /
documentation, PPT, Ongoing
Docs / Pitch
Q&A prep
6. Known Risks & Honest Scoping
Notes
No real DRDO/classified engine data available.
Solution uses realistic simulated data; explicitly

framed in pitch as "designed to be recalibrated
with real operational data upon deployment."
RTL (Return to Land) logic is decision-support
only — system recommends, operator/GCS
confirms. Not full autonomy (certification/safety
concern if claimed otherwise).
OEM data-sharing framed as manufacturer
engineering/degradation documentation — not
classified cross-nation operational data.
Engine-agnostic design — parameter mapping +
threshold calibration per engine type, so it works
whether the UAV fleet uses indigenous or
imported piston engines.