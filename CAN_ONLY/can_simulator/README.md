# UAV Engine Telemetry CAN Simulator

This module provides a standalone demonstration of a UAV engine telemetry pipeline using Linux SocketCAN. It is designed to showcase how engine sensor data can be generated, encoded into CAN frames using a DBC file, transmitted over a virtual CAN bus, and then decoded back into human-readable engineering values.

## Architecture
The pipeline follows this flow:
**Synthetic Telemetry Generation** $\rightarrow$ **CAN DBC Encoding** $\rightarrow$ **Linux SocketCAN (vcan0)** $\rightarrow$ **CAN Receiver** $\rightarrow$ **DBC Decoding** $\rightarrow$ **Real-time Monitoring**

## Technical Details

### Virtual CAN (vcan0)
We use `vcan0` (virtual CAN) to simulate a physical CAN bus on a Linux machine without requiring specialized hardware. This proves the communication architecture remains identical to a real-world deployment.

### CAN Message Structure (DBC)
The `uav_engine.dbc` file is the single source of truth. Signals are grouped logically into frames:

| CAN ID | Message Name | Signals | Units |
| :--- | :--- | :--- | :--- |
| `0x100` | `ENGINE_CORE` | RPM, EngineLoad, Throttle | rpm, %, % |
| `0x101` | `TEMPERATURES` | CHT, EGT | degC, degC |
| `0x102` | `LUBRICATION` | OilPressure, OilTemperature | kPa, degC |
| `0x103` | `FUEL` | FuelFlow, FuelPressure, AFR | L/h, kPa, - |
| `0x104` | `VIBRATION` | EngineVibration | mm/s |
| `0x105` | `ELECTRICAL` | BatteryVoltage, AlternatorVoltage | V, V |
| `0x106` | `ENVIRONMENT` | Altitude, AmbientTemperature | m, degC |

### Telemetry Generation
The simulator uses a correlated signal model. Instead of random values, parameters evolve based on physical approximations:
- **Throttle** drives **RPM** and **Fuel Flow**.
- **RPM** influences **CHT**, **EGT**, **Oil Pressure**, and **Vibration**.
- **Altitude** affects **Ambient Temperature**.
- **Oil Temperature** inversely affects **Oil Pressure**.

## How to Run the Demonstration

### 1. Setup the Virtual CAN Bus
Run the setup script to load the kernel module and initialize `vcan0`.
```bash
./setup_vcan.sh
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Start the Receiver (Monitor)
Open a terminal and start the decoded telemetry receiver:
```bash
# Note: Since this is a package-like structure, run from the CAN_ONLY directory
python3 -m can_simulator.receiver
```

### 4. Start the Simulator (Transmitter)
Open another terminal and start the telemetry generator:
```bash
python3 -m can_simulator.simulator
```

### 5. (Optional) Monitor Raw CAN Frames
To see the actual binary frames traveling on the bus:
```bash
python3 -m can_simulator.can_monitor
```

## Real-world Mapping
In a real UAV:
1. **Simulator** $\rightarrow$ Replaced by an **Engine Control Unit (ECU)** reading physical sensors.
2. **vcan0** $\rightarrow$ Replaced by a **Physical CAN Bus** (twisted pair wires).
3. **Receiver** $\rightarrow$ Replaced by a **Flight Controller** or **Telemetry Ground Station**.
4. **DBC** $\rightarrow$ Shared across all components to ensure correct data interpretation.

**Disclaimer:** This is a synthetic UAV engine telemetry CAN interface designed to demonstrate the communication architecture. The IDs and signals are for demonstration purposes and do not represent a proprietary UAV specification.
