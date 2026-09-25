# API Reference

## Backend

| Method | Route | Result |
| --- | --- | --- |
| GET | `/api/health` | Health and heartbeat age. |
| GET | `/api/latest-readings` | Recent persisted readings. |
| GET | `/api/events` | Event history. |
| GET | `/api/physics-status` | Physics expected/deviation/status data. |
| GET | `/api/ml-status` | ML warm-up and latest model output. |
| GET | `/api/fault-predictions` | Rule alert and parameter-level rule evidence. |
| WS | `/ws/live` | Telemetry and fault event stream. |

## Simulator

| Method | Route | Result |
| --- | --- | --- |
| POST | `/control/start-mission` | Starts/restarts a mission. |
| POST | `/control/fault` | Injects a live fault. |
| POST | `/control/fault/clear` | Clears a live fault. |
| GET | `/control/status` | Current mission snapshot. |
| GET | `/control/datasets` | Available datasets. |
| GET | `/control/config` | Dataset stage/environment configuration. |
| POST | `/control/training-data` | Streams raw training CSV. |

## Example Training Request

```json
{
  "dataset_id": "rotax914_baseline_dataset",
  "environment": "hot_high_altitude",
  "flights": 50,
  "packets_per_flight": 1000,
  "faults": [
    {"channel":"oil_pressure_psi","percent":-25,"start_stage":"TAKEOFF","end_stage":"CLIMB"}
  ]
}
```
