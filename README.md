# UAV Engine Digital Twin

An end-to-end UAV engine telemetry system with a synthetic engine simulator, SocketCAN transport, FastAPI receiver, and a live React dashboard.

## Architecture

The system follows a data-pipeline approach to simulate and monitor engine health:

```text
Simulator (CAN Producer) ➔ vcan0 (Virtual CAN Bus) ➔ FastAPI Receiver (CAN Consumer) ➔ React Dashboard (UI)
```

- **Simulator**: Generates synthetic engine telemetry (RPM, Temp, Pressure) and injects faults.
- **vcan0**: A Linux SocketCAN virtual interface that mimics a real physical CAN bus.
- **FastAPI Backend**: Listens to the CAN bus, decodes signals, and stores telemetry in PostgreSQL.
- **React Dashboard**: Provides real-time visualization of the engine state.

---

## Quick Start (Linux)

If you are on a native Linux system:

### 1. Prerequisites
Ensure you have the following installed:
- Python 3.10+
- Node.js 18+ & npm
- Docker & Docker Compose
- SocketCAN tools (`iproute2`, `kmod`)

### 2. First Run
From the repository root:
```bash
make db-up       # Start PostgreSQL database
make install     # Install Python and Node dependencies
make can-up      # Setup the virtual CAN interface (vcan0)
make dev         # Launch simulator, backend, and dashboard
```
Open [http://localhost:5173](http://localhost:5173) to view the dashboard.

---

## Windows Setup Guide (Step-by-Step)

This project relies on **SocketCAN**, which is a Linux-only kernel feature. To run it on Windows, you must use **WSL2 (Windows Subsystem for Linux)**.

### Step 1: Install WSL2 & Ubuntu
If you don't have WSL installed:
1. Open **PowerShell** as Administrator.
2. Run the following command:
   ```powershell
   wsl --install -d Ubuntu
   ```
3. Restart your computer if prompted.
4. Open the **Ubuntu** app from your Start Menu and follow the prompts to create a username and password.

### Step 2: Install Linux Dependencies
Inside your **Ubuntu terminal**, run:
```bash
sudo apt update
sudo apt install -y make python3 python3-pip nodejs npm iproute2 kmod
```

### Step 3: Setup Docker Desktop
1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
2. In Docker Desktop settings:
   - Go to **General** $\rightarrow$ Check **"Use the WSL 2 based engine"**.
   - Go to **Resources** $\rightarrow$ **WSL Integration** $\rightarrow$ Enable integration for your **Ubuntu** distribution.
3. Verify Docker is working in the Ubuntu terminal:
   ```bash
   docker --version
   ```

### Step 4: Running the Project
1. Navigate to your project folder. If your project is on the `D:` drive, it will be at:
   ```bash
   cd /mnt/d/Akshat/College/SIH26054
   ```
2. Run the setup commands:
   ```bash
   make db-up
   make install
   make can-up
   make dev
   ```

---

## Understanding vcan (Virtual CAN)

`vcan` is a virtual CAN interface that allows you to develop and test CAN applications without needing physical hardware (like an ECU or a USB-to-CAN adapter).

### How it works
- `make can-up` executes `sudo modprobe vcan`, which loads the virtual CAN kernel module.
- It then creates a network interface called `vcan0`.
- The simulator sends packets to `vcan0`, and the backend reads them from `vcan0`, exactly as they would if they were on a real wire.

### Troubleshooting vcan on WSL2
The default WSL2 kernel **does not always include the `vcan` module**. If `make can-up` fails with an error like `modprobe: FATAL: Module vcan not found`, you have two options:

1. **Use a Native Linux Machine/VM**: This is the most reliable way to use SocketCAN.
2. **Custom WSL2 Kernel**: You will need to compile your own WSL2 kernel with `CONFIG_CAN=y` and `CONFIG_CAN_VCAN=m` enabled. (This is an advanced task; if you are a beginner, using a VirtualBox VM with Ubuntu is recommended).

---

## Commands Reference

| Command | Description |
| :--- | :--- |
| `make install` | Install all Python and Node dependencies |
| `make db-up` | Start local PostgreSQL via Docker Compose |
| `make db-down` | Stop local PostgreSQL |
| `make can-up` | Create the `vcan0` interface (Linux/WSL) |
| `make can-down` | Remove the `vcan0` interface |
| `make dev` | Run Simulator + Backend + Dashboard together |
| `make simulator` | Run only the CAN simulator |
| `make backend` | Run only the FastAPI receiver (:8000) |
| `make frontend` | Run only the React dashboard (:5173) |
| `make generate-data` | Create labelled ML training data in PostgreSQL |
| `make generate-ideal-flights` | Create ideal no-fault flight data in PostgreSQL |
| `make check` | Run tests and type validation |
| `make build` | Build production frontend assets |

*Tip: Use `CAN_INTERFACE=can0 make backend` to connect to real hardware.*

---

## Simulator Controls

The simulator runs at ~10 Hz. Start it with `make simulator` and use these commands in the terminal:

**Startup Faults:**
```bash
make simulator SIMULATOR_ARGS="--fault overheating:1"
```

**Runtime Commands:**
- `throttle <0.0-1.0>` $\rightarrow$ Change engine throttle
- `altitude <meters>` $\rightarrow$ Change flight altitude
- `ambient_temp <celsius>` $\rightarrow$ Change air temperature
- `load <0.0-1.0>` $\rightarrow$ Change engine load
- `health <0.0-1.0>` $\rightarrow$ Change overall engine health
- `fault <fault_name> <severity>` $\rightarrow$ Inject a fault (e.g., `fault overheating 0.8`)
- `fault off <fault_name>` $\rightarrow$ Remove a fault
- `faults` $\rightarrow$ List active faults
- `status` $\rightarrow$ Current engine state
- `quit` $\rightarrow$ Stop simulator

**Available Faults**: `injector_degradation`, `overheating`, `lubrication_problem`, `vibration_fault`, `sensor_drift`.

---

## ML Training Data

The system can generate static, labelled datasets for training ML models without needing the live CAN bus.

- **Ideal Data**: `make generate-ideal-flights` generates telemetry for perfect flights.
- **Faulty/Climate Data**: `make generate-data` generates all combinations of faults across different climate profiles (e.g., Tropical, Arctic, Desert).

The data is stored in PostgreSQL in the `training_scenarios` and `training_telemetry` tables, combining CAN sensor data with ground-truth labels and climatic context.

---

## Repository Layout

```text
.
├── uav-engine-digital-twin/   # Engine physics simulator & CAN producer
├── DashboardCode/
│   ├── backend/               # CAN receiver, decoder, and FastAPI API
│   ├── frontend/              # React dashboard
│   ├── ml/                    # ML model training & inference
│   └── data/                  # Archived prototype data
├── scripts/                   # Bash/Python orchestration scripts
├── docs/                      # Design and reference documents
└── Makefile                   # Main entry point for all commands
```

---

## Notes

This is a synthetic engineering prototype. The simulator uses physically plausible relationships, but its thresholds and output are not validated for use in real aircraft. Replace the simulator with a real ECU/CAN source only after proper hardware and safety validation.
