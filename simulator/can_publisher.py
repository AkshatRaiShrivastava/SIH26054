from __future__ import annotations

import os
import time
from typing import Any

import can

from dbc import uav_engine as dbc_module


class SimCANPublisher:
    def __init__(self, interface: str = "vcan0"):
        self.interface = interface
        self.bus = can.ThreadSafeBus(interface="socketcan", channel=self.interface)
        self.dbc = dbc_module

    def send_frame(self, frame: Any):
        self.bus.send(frame)

    def send_packet(self, payload: dict):
        msg = can.Message(arbitration_id=payload["arbitration_id"], data=payload["data"], is_extended_id=False)
        self.bus.send(msg)

    def close(self):
        self.bus.shutdown()
