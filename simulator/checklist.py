from __future__ import annotations

CHECKLIST_BITS = {
    0: "oil_pressure_temp",
    1: "fuel_flow",
    2: "rpm_stability",
    3: "battery_alternator",
    4: "vibration",
    5: "can_communication",
    6: "ecu_fadec_handshake",
    7: "injection_timing",
}


def build_checklist_bitmask(values: dict) -> int:
    mask = 0
    for bit, name in CHECKLIST_BITS.items():
        if values.get(name, True):
            mask |= (1 << bit)
    return mask


def checklist_failed(values: dict) -> bool:
    return not all(values.get(name, True) for name in CHECKLIST_BITS.values())
