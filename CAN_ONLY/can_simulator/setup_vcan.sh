#!/bin/bash

# Setup script for virtual CAN (vcan0)
# Requires sudo privileges

echo "Setting up virtual CAN interface vcan0..."

# 1. Load vcan kernel module
if ! lsmod | grep -q vcan; then
    echo "Loading vcan module..."
    sudo modprobe vcan
else
    echo "vcan module already loaded."
fi

# 2. Create vcan0 interface if it does not exist
if ! ip link show vcan0 > /dev/null 2>&1; then
    echo "Creating vcan0 interface..."
    sudo ip link add dev vcan0 type vcan
else
    echo "vcan0 interface already exists."
fi

# 3. Bring vcan0 UP
echo "Bringing vcan0 UP..."
sudo ip link set up vcan0

# Verify
if ip link show vcan0 | grep -q "UP"; then
    echo "SUCCESS: vcan0 is UP and ready."
else
    echo "ERROR: Failed to bring vcan0 UP."
    exit 1
fi
