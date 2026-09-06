#!/bin/sh
# This script initializes the vcan0 interface on the host machine.
# It must be run in a privileged container with network_mode: host.

INTERFACE_NAME="${CAN_INTERFACE:-vcan0}"

echo "[CAN-INIT] Initializing $INTERFACE_NAME..."

# Load vcan module
if ! lsmod | grep -q vcan; then
    echo "[CAN-INIT] Loading vcan kernel module..."
    modprobe vcan || { echo "[CAN-INIT] Failed to load vcan module"; exit 1; }
fi

# Create vcan interface
if ip link show "$INTERFACE_NAME" >/dev/null 2>&1; then
    echo "[CAN-INIT] $INTERFACE_NAME already exists."
else
    echo "[CAN-INIT] Creating $INTERFACE_NAME..."
    ip link add dev "$INTERFACE_NAME" type vcan || { echo "[CAN-INIT] Failed to create vcan interface"; exit 1; }
fi

# Set interface up
echo "[CAN-INIT] Setting $INTERFACE_NAME up..."
ip link set up "$INTERFACE_NAME" || { echo "[CAN-INIT] Failed to set interface up"; exit 1; }

echo "[CAN-INIT] $INTERFACE_NAME is ready for use."
exit 0
