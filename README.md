# UAV Engine Digital Twin

An end-to-end UAV engine telemetry system with a synthetic engine simulator, SocketCAN transport, FastAPI receiver, and a live React dashboard. This is the only project README and the source of truth for running it.

## Supported architecture

```text
Simulator or real ECU -> vcan0/can0 -> FastAPI CAN receiver -> API/WebSocket -> React dashboard
```

The React application in `DashboardCode/frontend` is the only supported live dashboard. It receives normalized data from the FastAPI service; it never reads CAN directly. `DashboardCode/src/app/dashboard.py` is an archived Streamlit/SQLite prototype and must not be launched with the live stack.

## Run locally

### Requirements

- Linux with SocketCAN tools: `ip` and `modprobe`
- Python 3.10 or later
- Node.js 18 or later and npm
- Docker Engine with Docker Compose installed and running (for the project PostgreSQL service)
- Permission to run `sudo` when creating the virtual CAN interface

### First run

From the repository root:

```bash
make db-up
make install
make can-up
make dev
```

The project runs only on Linux. Windows users must use a WSL2 Linux distribution; do not run the bundled `make.exe` from PowerShell. The simulator, CAN receiver, `can-up`, and `dev` targets require Linux SocketCAN (`vcan`, `ip`, and `modprobe`) and Bash.

### Windows setup (WSL2)

1. In an elevated PowerShell window, install Ubuntu for WSL2:

   ```powershell
   wsl --install -d Ubuntu
   ```

   Restart if Windows asks, then open **Ubuntu** and complete the Linux username/password setup.

2. Install Make and the Linux prerequisites inside the Ubuntu/WSL terminal:

   ```bash
   sudo apt update
   sudo apt install -y make python3 python3-pip nodejs npm iproute2 kmod
   ```

3. Install Docker Desktop on Windows, enable **Use the WSL 2 based engine**, and enable WSL integration for the Ubuntu distribution in **Settings → Resources → WSL Integration**. Docker and Docker Compose will then be available in the Ubuntu/WSL terminal. Verify this with:

   ```bash
   docker --version
   docker compose version
   ```

4. From the repository in the WSL terminal (for example, `/mnt/d/Akshat/College/SIH26054`), run the normal Linux commands:

```bash
make db-up
make install
make can-up
make dev
```

Open http://localhost:5173 for the dashboard. API documentation is available at http://localhost:8000/docs.

`make dev` runs the simulator, CAN receiver/FastAPI backend, and React/Vite dashboard in one terminal. Press `Ctrl+C` once to stop all three processes. `make can-up` is normally needed once after each computer restart; it creates `vcan0` only when that interface does not already exist.

The default PostgreSQL database is started by `make db-up` and is available at `postgresql://uav:uav@localhost:5432/uav_telemetry`. To use a team-managed database, export `DATABASE_URL` before running any command; `.env.example` lists the expected values.

For a real ECU or a simulator with faults, leave the default label as `unknown`; the receiver cannot truthfully infer a fault label from CAN sensor data alone.

### To create a static dataset of 15 ideal, no-fault flights without starting CAN, the backend, or the frontend:

```bash
make generate-ideal-flights
```

It writes to PostgreSQL using the exact same `flights` and `flight_telemetry` schema as the live recorder. Each flight is an independent time series with 600 samples by default. Change the size or deliberately replace only previous ideal flights:

```bash
make generate-ideal-flights IDEAL_FLIGHT_ARGS="--flights 10 --steps 1000 --replace"
```

### Fault and climate-labelled flights

Generate static, labelled time-series data without requiring `vcan0` or a running dashboard:

```bash
make generate-data DATA_ARGS="--steps 300 --samples-per-scenario 3 --replace"
```

This creates all 32 combinations of the five supported faults (including `normal`) across eight representative UAV climate profiles: temperate, hot desert, humid monsoon, maritime coastal, cold/high altitude, hot/high altitude, tropical wet, and cold dry. With the defaults, it generates 768 scenarios and 230,400 time-series rows.

The output has two tables:

- `training_scenarios`: one row per climate/fault/input scenario with its exact labels and climate profile.
- `training_telemetry`: CAN-shaped sensor measurements joined with climate context and multi-label fault columns (`injector_degradation`, `overheating`, `lubrication_problem`, `vibration_fault`, `sensor_drift`).

CAN data remains sensor/hardware-only. Climate fields and fault truth labels are generated separately and stored alongside each sample specifically for supervised training; they are never implied to come from a real ECU. The script does not replace existing `training_*` tables unless `--replace` is passed. For a smaller smoke-test dataset use:

```bash
make generate-data DATA_ARGS="--steps 10 --samples-per-scenario 1 --replace"
```

### Real CAN hardware

Use the name of your SocketCAN adapter instead of `vcan0`:

```bash
CAN_INTERFACE=can0 make backend
make frontend
```

Do not run the simulator when a real ECU is transmitting. The backend is the sole CAN consumer. If you intentionally need a simulated full stack on a different interface, use:

```bash
CAN_INTERFACE=vcan1 make can-up
CAN_INTERFACE=vcan1 make dev
```

## Commands

```text
make install       Install all Python and Node dependencies
make db-up          Start local PostgreSQL with Docker Compose
make db-down        Stop local PostgreSQL
make can-up        Create the default local vcan0 interface
make dev           Run simulator + backend + dashboard together
make simulator     Run only the CAN simulator
make backend       Run only the CAN receiver/API on port 8000
make frontend      Run only the React dashboard on port 5173
make generate-data Create labelled climate/fault time-series PostgreSQL data
make generate-ideal-flights  Create ideal no-fault flight time-series PostgreSQL data
make check         Run active Python tests and TypeScript validation
make build         Create DashboardCode/frontend/dist production assets
make can-down      Remove the selected local virtual CAN interface
```

All commands accept `CAN_INTERFACE`; for example, `CAN_INTERFACE=can0 make backend`. The `check` target intentionally excludes the archived Streamlit prototype tests.

## Simulator controls

The simulator runs at roughly 10 Hz. Start it alone when you need to experiment with it:

```bash
make simulator
```

Start with one or more faults directly from Make:

```bash
make simulator SIMULATOR_ARGS="--fault overheating:1"
make simulator SIMULATOR_ARGS="--fault overheating:0.8 --fault vibration_fault:0.7"
make dev SIMULATOR_ARGS="--fault overheating:1 --fault lubrication_problem:0.8"
```

While it is running, enter commands in that terminal:

```text
throttle 0.8
altitude 3500
ambient_temp 25
load 0.7
health 0.95
fault injector_degradation 0.5
fault off injector_degradation
faults
status
quit
```

Fault choices are `injector_degradation`, `overheating`, `lubrication_problem`, `vibration_fault`, and `sensor_drift`. You can also choose one at startup, for example:

```bash
cd uav-engine-digital-twin
python main.py --interface vcan0 --fault overheating --severity 0.7
```

The CAN IDs, scaling, and signal validation ranges are defined in `uav-engine-digital-twin/config/can_mapping.yaml` and `DashboardCode/backend/config/can_mapping.yaml`. Keep those mappings aligned when adding a signal.

## Labelled ML training data

### Ideal flights from the live backend

Every backend start now creates a new `flight_id` in PostgreSQL. Complete sensor cycles are saved to `flights` and `flight_telemetry`; partial CAN frames are never written as rows. Stop the backend normally to mark the flight `complete`.

For a normal simulator run that you want to label explicitly as ideal, use:

```bash
FLIGHT_LABEL=ideal_no_fault make dev
```

## Repository layout

```text
.
├── uav-engine-digital-twin/   Engine physics simulator and CAN producer
├── DashboardCode/
│   ├── backend/               Sole CAN receiver, decoder, validator and FastAPI API
│   ├── frontend/              Supported user-facing dashboard (React)
│   ├── src/                   Archived SQLite/physics/Streamlit prototype
│   ├── ml/                    Model training and inference experiments
│   └── data/                  Archived prototype data, not the live CAN source
├── scripts/                   Development orchestration and SocketCAN helpers
├── docs/                      Design/reference documents
└── Makefile                   Stable project commands
```

Keep browser code in `DashboardCode/frontend`, CAN protocol and ingestion code in `DashboardCode/backend`, and simulator behavior in `uav-engine-digital-twin`.

## Notes

This is a synthetic engineering prototype. The simulator uses physically plausible relationships, but its thresholds and output are not validated for use in an aircraft. Replace the simulator with a real ECU/CAN source only after appropriate hardware, safety, and calibration validation.

my team has to train mutiple ML models for which they need static data in ideal conditions as well as on all the possible fault combinations and climatic conditions
so make some script through which we can generate the data in SQL in time series type as we are receiving the data from CAN simulator
through CAN we get only the sesnors and hardware info, not the climatic info
so we'll use all the possible climatic conditions in which a UAV can fly.
we have to combine both the data CAN and climate then generate the training data, which should be labelled data
