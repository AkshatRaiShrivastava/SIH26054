import os

# CAN Interface Configuration
CAN_INTERFACE = 'vcan0'

# Simulation Timing
TICK_RATE_HZ = 10  # Update rate for telemetry generation (10Hz)
SEND_INTERVAL = 1.0 / TICK_RATE_HZ

# DBC Path
DBC_FILE_PATH = os.path.join(os.path.dirname(__file__), 'dbc', 'uav_engine.dbc')

# Telemetry Constraints
RPM_MIN = 0
RPM_MAX = 20000

THROTTLE_MIN = 0
THROTTLE_MAX = 100

ALTITUDE_MAX = 12000
