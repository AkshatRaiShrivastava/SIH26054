# UAV Engine Digital Twin

A comprehensive digital twin for UAV engine telemetry, featuring real-time CAN ingestion, physics-based residual analysis, and flight history tracking.

## 🚀 Quick Start

The entire system is containerized for a "one-command" setup.

### 1. Clone the repository
```bash
git clone <repo-url>
cd SIH26054
```

### 2. Configure Environment
```bash
cp .env.example .env
# Optional: Edit .env to change passwords or ports
```

### 3. Start Everything
```bash
docker compose up --build
```

### 4. Access the Dashboard
Open your browser to: **[http://localhost:3000](http://localhost:3000)**

---

## 🛠️ Development Commands

| Command | Action |
| :--- | :--- |
| `make up` | Start the entire stack (equivalent to `docker compose up --build`) |
| `make logs` | View real-time logs from all services |
| `make down` | Stop the services (preserves database data) |
| `make down-vol` | Stop services and **wipe all flight history** |
| `make clean` | Complete cleanup of containers and volumes |

---

## 📐 Architecture

The system uses a modular Docker Compose architecture:

- **`can-init`**: (Privileged) Configures the Linux `vcan0` interface on the host.
- **`uav-simulator`**: Acts as a fake ECU, pushing SocketCAN frames to `vcan0`.
- **`uav-backend`**: Fast API server that decodes CAN, runs physics, and stores data.
- **`uav-telemetry-postgres`**: Persistent PostgreSQL storage for flight history.
- **`uav-frontend`**: React dashboard for live monitoring and history analysis.

### Data Flow
`Simulator` $\rightarrow$ `vcan0` $\rightarrow$ `Backend` $\rightarrow$ `PostgreSQL` $\rightarrow$ `React Dashboard`

---

## 🧪 Acceptance Criteria Verification

To verify the system is working:
1. Run `docker compose up --build`.
2. Navigate to `http://localhost:3000`.
3. Click **START NEW SIMULATION**.
4. Verify a **Flight ID** (e.g., `FLT-2026...`) appears.
5. Observe **CAN Telemetry** and **Physics Residuals** updating in real-time.
6. Click **STOP SIMULATION**.
7. Go to **FLIGHT HISTORY** and verify the completed flight is listed.
8. Click the flight to view historical telemetry.
