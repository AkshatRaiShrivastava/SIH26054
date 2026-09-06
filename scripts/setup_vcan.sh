#!/usr/bin/env bash
set -euo pipefail
sudo ip link add dev vcan0 type vcan >/dev/null 2>&1 || true
sudo ip link set up vcan0 >/dev/null 2>&1 || true
ip link show vcan0 || true
