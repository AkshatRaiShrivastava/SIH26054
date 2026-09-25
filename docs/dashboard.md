# Dashboard

The dashboard at `/dashboard/` shows live propulsion health derived by the backend.

## Sections

| Section | Function |
| --- | --- |
| Flight state | RPM, altitude, ambient temperature, air-density ratio. |
| Live engine channels | Actual sensor values vs physics-twin expected values. |
| Physics trend | Actual solid line vs expected dashed line. |
| Physics intelligence | Overall and per-channel health state. |
| ML anomaly detection | Isolation Forest score and hybrid ML/rule decision. |
| Fault prediction & rule evidence | Category, confidence, direction, deviation %, matched features. |
| Event timeline | Fault and stage events. |

## Live State

Green `Live WebSocket` means the browser receives server-pushed telemetry. Heartbeat age comes from the authenticated simulator heartbeat and is `None` until a mission is started.

## Rule Evidence

After the first 15 packets, the ML model returns rule evidence. Each row explains how a parameter differed from its healthy baseline and whether it matched the named fault signature. RUL is not shown because the supplied model does not perform prognostics.
