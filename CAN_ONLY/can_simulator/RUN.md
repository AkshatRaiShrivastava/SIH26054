# Quick Start: UAV CAN Simulator

Run these commands from within the `can_simulator/` directory.

### 1. Setup Virtual CAN Bus
Initialize the `vcan0` interface (requires sudo):
```bash
sudo ./setup_vcan.sh
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Components
Open three separate terminals and run the following in order:

**Terminal 1: The Receiver (Decoded Telemetry)**
```bash
python3 receiver.py
```

**Terminal 2: The Simulator (Data Transmitter)**
```bash
python3 simulator.py
```

**Terminal 3: The Monitor (Raw CAN Frames)**
```bash
python3 can_monitor.py
```
