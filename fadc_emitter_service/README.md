# FADEC Emitter Service (Node + TypeScript)

This repository contains a **stand‑alone** FADEC (Full Authority Digital Engine
Control) emitter written in Node.js with TypeScript. It replaces the original
Python CAN‑bus implementation with a WebSocket‑based telemetry stream and
provides a small REST control surface.

## Features

* **In‑memory** mission simulation – no external database required.
* **Telemetry** generated at 10 Hz, encrypted with **AES‑256‑GCM**. The key is
  taken from the environment variable `FADEC_CAN_KEY` (the same format used by
  the original Python scripts – a 64‑character hex string or a base64‑encoded
  32‑byte key).
* **WebSocket** endpoint (`/ws`) broadcasting three frame types:
  * `telemetry` – encrypted telemetry payload.
  * `heartbeat` – simple keep‑alive every second.
  * `fault_event` – emitted when a fault is set via the REST API.
* **REST control API** (`/control/*`):
  * `POST /control/start-mission` – optional JSON `{ "durationSec": <number> }`.
  * `POST /control/stop-mission`
  * `POST /control/fault` – JSON `{ "fault": "<string>" }`.
  * `POST /control/fault/clear`
  * `GET  /control/status` – current mission state.
* **Health endpoint** (`GET /health`) for monitoring / Vercel.
* **Vercel‑ready** – a `vercel.json` is provided; `vercel` will run `npm start`
  (listening on the port supplied by `process.env.PORT`).

## Local development

```bash
# Install dependencies
npm install

# Build the TypeScript sources
npm run build

# Run the service (default port 3000)
npm start

# Or run directly with ts-node-dev for hot‑reloading
npm run dev
```

The service expects the environment variable `FADEC_CAN_KEY` to be set. The
original scripts generate a hex key with:

```bash
FADEC_CAN_KEY=$(python - <<'PY'
import secrets, sys
sys.stdout.write(secrets.token_hex(32))
PY
)
export FADEC_CAN_KEY
```

You can also provide a base64‑encoded key – the service will detect the format
automatically.

## Vercel deployment

1. Install the Vercel CLI (`npm i -g vercel`).
2. From the project root run `vercel` and follow the prompts. Vercel will use the
   `start` script (`node dist/index.js`).
3. Set the environment variable `FADEC_CAN_KEY` in the Vercel dashboard (Settings →
   Environment Variables). The variable must be **plain** (no quotes).
4. After deployment, the WebSocket endpoint will be available at
   `wss://<your‑deployment>.vercel.app/ws`.

> **Note**: Vercel’s serverless platform imposes a request timeout (default 60 s).
> Long‑running WebSocket connections are supported, but keep‑alive traffic is
> required to avoid idle termination. The service sends a heartbeat every
> second, which satisfies Vercel’s requirements.

## License

MIT – feel free to adapt for your own UAV simulation projects.
