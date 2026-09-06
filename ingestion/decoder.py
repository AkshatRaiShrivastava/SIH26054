from __future__ import annotations

import os

from cantools.database import load_file

DBC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dbc", "uav_engine.dbc")
db = load_file(DBC_PATH, strict=False)


def decode_can_message(msg) -> dict:
    decoded = db.decode_message(msg.arbitration_id, msg.data)
    cleaned = {}
    for key, value in decoded.items():
        numeric_value = getattr(value, "value", value)
        cleaned[str(key)] = float(numeric_value)
    return cleaned
