# Simulator Commands Reference

This document lists all the commands used to operate the UAV Engine Digital Twin simulator and the overall pipeline.

## 🚀 Quick Start (via Makefile)

The easiest way to run the system is using the `make` targets.

| Target | Command | Description |
| :--- | :--- | :--- |
| **Setup** | `make install` | Install all Python and frontend dependencies |
| | `make db-up` | Start PostgreSQL database via Docker |
| | `make can-up` | Configure `vcan0` interface (Linux) |
| **Runs** | `make sim-normal` | Run a standard surveillance mission |
| | `make sim-fault` | Run a mission with injector degradation |
| | `make sim-record` | Run a mission and save results to `output.csv` |
| | `make simulator` | Run custom simulation (use `SIMULATOR_ARGS`) |
| | `make backend` | Start the CAN receiver and API backend |
| | `make frontend` | Launch the original React monitoring dashboard |
| | `make streamlit` | Launch the Main Admin Console (Recommended) |
| | `make dev` | Run the full pipeline (Sim $\rightarrow$ Backend $\rightarrow$ UI) |
| **Utils** | `make check` | Run all tests (Python & TypeScript) |
| | `make build` | Build the production frontend |

---

## 🛠️ Advanced Simulator Usage

If you are running the simulator directly via Python, use the following flags:

**Basic Execution:**
```bash
python uav-engine-digital-twin/main.py --mission <profile>
```

### Available Arguments:

| Argument | Default | Description | Example |
| :--- | :--- | :--- | :--- |
| `--mission` | `surveillance` | Mission profile from `config/missions/` | `--mission endurance` |
| `--speed` | `1.0` | Simulation speed multiplier | `--speed 10` (10x faster) |
| `--seed` | `None` | Random seed for reproducible runs | `--seed 42` |
| `--record` | `None` | Path to save true and measured states | `--record flight_001.csv` |
| `--fault` | `[]` | Inject a fault (`NAME[:SEVERITY]`) | `--fault cooling_degradation:0.5` |
| `--interface` | `vcan0` | SocketCAN interface name | `--interface vcan1` |

### Example Scenarios:

**1. Fast-forwarded surveillance mission:**
```bash
python uav-engine-digital-twin/main.py --mission surveillance --speed 5
```

**2. High-severity lubrication failure with recording:**
```bash
python uav-engine-digital-twin/main.py --mission surveillance --fault lubrication_degradation:0.9 --record failure_log.csv
```

**3. Deterministic run for ML training:**
```bash
python uav-engine-digital-twin/main.py --mission endurance --seed 123 --record training_data.csv
```

---

## 📡 Pipeline Orchestration

To see the data flow in real-time, run the components in this order:

1. **Database**: `make db-up`
2. **CAN Interface**: `make can-up`
3. **Backend**: `make backend`
4. **Simulator**: `make sim-normal`
5. **Admin Console**: `make streamlit`
