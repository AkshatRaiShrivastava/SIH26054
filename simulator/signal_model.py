from __future__ import annotations

import math

from physics.atmosphere import ambient_temperature_c
from simulator.mission_profile import phase_for_elapsed


def clamp(value, low, high):
    return max(low, min(high, value))


def phase_target_state(elapsed_s: float, phase_id: int, throttle: float, load: float, altitude_m: float, scenario: str):
    if phase_id == 0:
        rpm = 700 + throttle * 0.8
        fuel_flow = 9.0 + throttle * 0.08
        alt = 0.0
        ambient = 15.0
    elif phase_id == 1:
        rpm = 1200 + throttle * 0.6
        fuel_flow = 10.0 + throttle * 0.09
        alt = 0.0
        ambient = ambient_temperature_c(altitude_m)
    elif phase_id == 2:
        rpm = 2600 + throttle * 1.4
        fuel_flow = 12.0 + throttle * 0.12
        alt = 200.0
        ambient = ambient_temperature_c(altitude_m)
    elif phase_id == 3:
        rpm = 3200 + throttle * 1.7
        fuel_flow = 14.0 + throttle * 0.16
        alt = 2000.0 + (elapsed_s - 360) * 0.8
        ambient = ambient_temperature_c(altitude_m)
    elif phase_id == 4:
        rpm = 4300 + throttle * 0.7
        fuel_flow = 17.0 + throttle * 0.16
        alt = 4200.0
        ambient = ambient_temperature_c(altitude_m)
    elif phase_id == 5:
        rpm = 3000 + throttle * 0.5
        fuel_flow = 12.0 + throttle * 0.11
        alt = max(0.0, 4200.0 - (elapsed_s - 3240) * 1.8)
        ambient = ambient_temperature_c(altitude_m)
    else:
        rpm = 900
        fuel_flow = 8.0
        alt = 0.0
        ambient = 15.0

    if scenario == "overheating":
        rpm += 180
        fuel_flow += 1.5
    elif scenario == "misfire":
        rpm -= 220
        fuel_flow -= 1.0
    elif scenario == "electrical-issue":
        rpm += 50
    elif scenario == "sensor-drift":
        ambient += 4.0
    return {"rpm": rpm, "fuel_flow": fuel_flow, "altitude_m": alt, "ambient_temp_c": ambient}


def simulate_tick(elapsed_s: float, previous: dict, scenario: str, health_index: float = 100.0, fault_severity: float = 0.0, phase_durations_s: dict[int, float] | None = None):
    phase_id = phase_for_elapsed(elapsed_s, phase_durations_s)
    throttle = 25.0 + 50.0 * (1.0 if phase_id >= 2 else 0.5)
    load = 35.0 + (elapsed_s / 3600.0) * 60.0
    altitude = 0.0
    if phase_id == 3:
        altitude = 2000.0 + (elapsed_s - 360) * 0.8
    elif phase_id == 4:
        altitude = 4200.0
    elif phase_id == 5:
        altitude = max(0.0, 4200.0 - (elapsed_s - 3240) * 1.8)

    target = phase_target_state(elapsed_s, phase_id, throttle, load, altitude, scenario)
    rpm = previous.get("rpm", 0.0) * 0.7 + target["rpm"] * 0.3
    rpm = clamp(rpm, 600.0, 5200.0)

    fuel_flow = previous.get("fuel_flow", 0.0) * 0.82 + target["fuel_flow"] * 0.18
    fuel_flow = clamp(fuel_flow, 0.0, 40.0)

    cht_c = previous.get("cht_c", 80.0) * 0.86 + (60.0 + rpm * 0.016 + altitude * 0.006 + 8.0 * max(0, (100.0 - health_index) / 20.0)) * 0.14
    egt_c = previous.get("egt_c", 550.0) * 0.88 + (500.0 + rpm * 0.05 + (100.0 - health_index) * 2.0) * 0.12
    oil_temp = previous.get("oil_temperature_c", 70.0) * 0.9 + (72.0 + rpm * 0.005 + load * 0.18) * 0.1
    oil_pressure = previous.get("oil_pressure_kpa", 350.0) * 0.9 + (380.0 + (3500 - rpm) * 0.04 + load * 0.6) * 0.1

    if scenario == "lubrication-degradation":
        oil_pressure -= 70.0 * fault_severity
        oil_temp += 12.0 * fault_severity
    if scenario == "injector-degradation":
        egt_c += 30.0 * fault_severity
        fuel_flow += 1.5 * fault_severity
    if scenario == "vibration-degradation":
        pass
    if scenario == "overheating":
        cht_c += 25.0 * fault_severity
        egt_c += 35.0 * fault_severity
    if scenario == "misfire":
        egt_c += 18.0 * fault_severity
        rpm += 150.0 * math.sin(elapsed_s / 30.0) * fault_severity
    if scenario == "electrical-issue":
        pass
    if scenario == "sensor-drift":
        egt_c += 25.0 * fault_severity
    if scenario == "degradation-demo":
        oil_pressure -= 10.0 + elapsed_s / 180.0
        egt_c += 0.08 * elapsed_s
        cht_c += 0.06 * elapsed_s

    vibration = previous.get("vibration_mms", 1.0) * 0.85 + (1.2 + rpm * 0.00035 + abs(egt_c - 650.0) * 0.002 + max(0.0, (100.0 - health_index) / 12.0)) * 0.15
    if scenario == "vibration-degradation":
        vibration += 0.8 * fault_severity
    if scenario == "misfire":
        vibration += 0.7 * fault_severity

    afr = 14.7 + (35.0 - rpm * 0.0015) * 0.02
    if scenario == "injector-degradation":
        afr -= 0.9 * fault_severity
    battery_voltage = 13.9 + (rpm / 15000.0) * 2.0
    if scenario == "electrical-issue":
        battery_voltage -= 2.2 * fault_severity
    if scenario == "sensor-drift":
        battery_voltage += 0.5 * fault_severity

    result = {
        "rpm": round(rpm, 2),
        "cht_c": round(cht_c, 2),
        "egt_c": round(egt_c, 2),
        "oil_pressure_kpa": round(oil_pressure, 2),
        "oil_temperature_c": round(oil_temp, 2),
        "fuel_flow_lph": round(fuel_flow, 2),
        "vibration_mms": round(vibration, 2),
        "afr": round(afr, 2),
        "battery_voltage": round(battery_voltage, 2),
        "altitude_m": round(altitude, 2),
        "ambient_temp_c": round(max(-30.0, ambient_temperature_c(altitude, 15.0)), 2),
        "phase_id": phase_id,
        "throttle": round(throttle, 2),
        "engine_load": round(load, 2),
    }
    return result
