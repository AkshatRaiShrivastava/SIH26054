# Architecture

## Services

| Service | Role |
| --- | --- |
| Simulator | FastAPI mission control and FADEC raw telemetry transmitter. |
| Backend | SocketCAN receiver, independent physics, ML inference, REST/WebSocket server. |
| PostgreSQL | Telemetry, event, and CAN audit persistence. |
| Simulator Console | Test-harness UI. |
| Dashboard | Product monitoring UI. |
| Landing | Root page with route choices. |
| Nginx | Public reverse proxy. |

## Data Path

1. Operator configures a dataset, environment, duration overrides, and optional live faults in the simulator.
2. The simulator generates raw engine and electrical readings.
3. FADEC encrypts telemetry/heartbeat/fault events with AES-256-GCM and fragments them into classic CAN frames on `vcan0`.
4. Backend reassembles and authenticates frames. Invalid frames are audited and discarded.
5. Backend computes expected values independently, persists results, broadcasts live telemetry, and runs the ML model.
6. Dashboard consumes WebSocket data and REST fallback endpoints.

## Design Rule

Raw telemetry travels across CAN. Expected values, deviations, health state, physics trend, and ML decision are backend-derived fields. EGT expectation uses nominal AFR by stage because no live AFR sensor is carried in the CAN contract.

## Public Routes

| Route | Purpose |
| --- | --- |
| `/` | Landing page |
| `/dashboard/` | Product dashboard |
| `/simulator/` | Simulator console |
| `/api/` | Backend REST API |
| `/ws/live` | Backend WebSocket |
| `/control/` | Simulator API |
