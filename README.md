SIH UAV Simulation
===================
---

**Enjoy the simulation!**
---

## 1️⃣ Prerequisites

| Tool | Install command |
|------|-----------------|
| Python 3.12+ | `sudo apt-get install -y python3 python3-venv python3-pip` |
| pipenv (optional) | `pip install --user pipenv` |
| iproute2 (virtual CAN) | `sudo apt-get install -y iproute2` |
| kmod (load kernel modules) | `sudo apt-get install -y kmod` |
| Docker (only for PostgreSQL) | Follow Docker’s official install script or `sudo apt-get install -y docker.io` |

---

## 2️⃣ Create a Python virtual environment and install dependencies

```bash
# From the repository root
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r EngineSimulator/requirements.txt
pip install -r UserDashboardWorkspace/requirements.txt
```

All required packages (`python‑can`, `cryptography`, `fastapi`, `uvicorn`, etc.) are now installed inside `.venv`.

---

## 3️⃣ (Optional) Start a PostgreSQL container

If you want persistent storage, run PostgreSQL in Docker – this is the **only** Docker usage required.

```bash
docker pull postgres:16-alpine

docker run -d \
	--name uav-postgres \
	-e POSTGRES_USER=postgres \
	-e POSTGRES_PASSWORD=postgres \
	-e POSTGRES_DB=uav \
	-p 5432:5432 \
	postgres:16-alpine
```

The backend expects the connection string:

```
postgresql://postgres:postgres@localhost:5432/uav
```

If you use a different DB name, user, or password, export `DATABASE_URL` before starting the backend (see step 5).

---

## 4️⃣ Create a virtual CAN interface (`vcan0`)

```bash
sudo modprobe vcan          # load the vcan kernel module
sudo ip link add dev vcan0 type vcan
sudo ip link set up vcan0
# Verify it exists
ip -details link show vcan0
```

> **Note:** `vcan0` must exist **before** starting the FADEC transmitter or the backend; otherwise they will fail to open the CAN socket.

---

## 5️⃣ Launch the FastAPI backend (serves the dashboard)

```bash
cd UserDashboardWorkspace
# If you did not start the PostgreSQL container, you can skip the DB or use an in‑memory store.
# To point the backend at a custom DB, uncomment and edit the line below:
# export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/uav"
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Leave this terminal running.  Open a browser at **http://localhost:8000/** – the dashboard UI should load and wait for live data.

---

## 6️⃣ Run the FADEC transmitter (engine → CAN)

Open a **new terminal** (still inside the same `.venv`):

```bash
# Export a shared encryption key (optional – if you want the same key across runs)
export FADEC_CAN_KEY=$(python - <<'PY'
import secrets, sys
sys.stdout.write(secrets.token_hex(32))
PY
)

# Start the transmitter – it runs for 2 seconds by default
python -m EngineSimulator.files.fadec_can --duration 2
```

The FADEC encrypts telemetry, fragments it into CAN frames, and publishes them on `vcan0`.  The backend from step 5 reads those frames, decrypts them, stores them in PostgreSQL (if running) and streams live updates to the dashboard via WebSocket.

---

## 7️⃣ Run the Engine Simulator UI (Flask frontend)

The Engine Simulator also ships a simple Flask UI that runs the mission once and streams telemetry to a web page.  Use the helper script we provide:

```bash
chmod +x run_engine_ui.sh   # only needed once
./run_engine_ui.sh
```

The script activates the virtual environment and starts the Flask development server on `http://localhost:5000/`.  Open that URL in a browser to view the interactive UI.

If you prefer to run the Flask app manually, remember to activate the environment first:

```bash
source .venv/bin/activate
export FLASK_APP=EngineSimulator/frontend/app.py
export FLASK_ENV=development
flask run --host 0.0.0.0 --port 5000
```

---

## 8️⃣ (Optional) Run the raw mission simulator without encryption

If you only want to see the mission data printed to the console, run:

```bash
python EngineSimulator/files/mission_simulator.py
```

This executes the mission profile and prints each stage – it does **not** interact with CAN.

---

## 8️⃣ Stopping the stack

| Component | How to stop |
|-----------|-------------|
| Backend (uvicorn) | Press `Ctrl‑C` in its terminal |
| FADEC process | Press `Ctrl‑C` in its terminal |
| PostgreSQL container | `docker stop uav-postgres && docker rm uav-postgres` |
| Virtual CAN interface | `sudo ip link delete vcan0` |
| Virtual environment | `deactivate` (optional) |

---

## 9️⃣ Project layout (top‑level)

```
SIH_UAV_Simulation/
├─ EngineSimulator/          # engine, FADEC, datasets, etc.
├─ UserDashboardWorkspace/    # FastAPI backend + static dashboard
├─ README.md                # this file
└─ .venv/ (created locally) # Python virtual environment
```

Feel free to adjust any command (e.g., change the FADEC `--duration` or supply a custom dataset via `--dataset <path>`).  All components are designed to work together out‑of‑the‑box.

---

**Enjoy the simulation!**
SIH UAV Simulation
=================

A Python‑based UAV engine‑simulation stack with FADEC, virtual CAN, FastAPI backend and a web dashboard.

Run the steps in the README for a full local setup.

---

## ☁️ Deploy the FADEC Emitter Service on Render

Render can host the **Node + TypeScript** FADEC emitter as a web service. The
configuration lives in `render.yaml` at the repository root. Follow these steps:

1. **Create a Render account** (or log in) at https://render.com.
2. **Add a new Web Service**:
	 * **Name** – e.g. `fadec-emitter-service`.
	 * **Region** – choose the nearest region.
	 * **Branch** – `main` (or the branch you want to deploy).
	 * **Root Directory** – leave blank (the repo root).
	 * **Build Command** – `cd fadc_emitter_service && npm install && npm run build`.
	 * **Start Command** – `cd fadc_emitter_service && npm start`.
	 * **Environment** – add a variable `FADEC_CAN_KEY` with a 64‑character hex
		 string (or base64‑encoded 32‑byte key). Example generation:

		 ```bash
		 python - <<'PY'
		 import secrets, sys
		 sys.stdout.write(secrets.token_hex(32))
		 PY
		 ```

	 * Render will expose the service on a port it provides via `$PORT`.
3. **Deploy** – click *Create Web Service*. Render will run the build command,
	 install dependencies, compile TypeScript, and start the service.
4. **Verify** – once the service is live, open the provided URL and append
	 `/ws` to test the WebSocket (e.g. `wss://<service>.onrender.com/ws`).
	 You can also hit `https://<service>.onrender.com/health` to see a JSON
	 `{"ok":true}` response.
5. **Optional – Connect the Engine Simulator**:
	 * The original Python FADEC script expects a CAN interface, which Render
		 cannot provide. Instead, point your local or cloud‑based engine simulator
		 to the Render WebSocket URL and use the same `FADEC_CAN_KEY` for encryption.
	 * Example (local simulator):

		 ```bash
		 export FADEC_CAN_KEY=<same-key-as-Render>
		 export FADEC_EMITTER_URL=wss://<service>.onrender.com/ws
		 python -m EngineSimulator.files.fadec_can --duration 5
		 ```

	 * The simulator will send encrypted telemetry over the WebSocket, and the
		 Render‑hosted service will broadcast it to any connected clients.

**Note:** Render’s free tier imposes a request timeout (default 60 seconds).
Because the service sends a heartbeat every second, the connection stays alive.
If you need longer‑running missions, consider a paid plan or keep the service
warm with a periodic ping.

---