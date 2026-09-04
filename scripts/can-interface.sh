#!/usr/bin/env bash
# Manage the local development SocketCAN interface used by this repository.
set -euo pipefail

interface_name="${CAN_INTERFACE:-vcan0}"
case "${1:-}" in
  up)
    if ip link show "$interface_name" >/dev/null 2>&1; then
      echo "$interface_name already exists."
      exit 0
    fi
    sudo modprobe vcan
    sudo ip link add dev "$interface_name" type vcan
    sudo ip link set up "$interface_name"
    echo "$interface_name is ready."
    ;;
  down)
    if ip link show "$interface_name" >/dev/null 2>&1; then
      sudo ip link delete "$interface_name"
      echo "$interface_name removed."
    else
      echo "$interface_name does not exist."
    fi
    ;;
  *) echo "Usage: $0 {up|down}" >&2; exit 2 ;;
esac
