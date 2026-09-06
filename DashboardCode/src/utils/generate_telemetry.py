"""
generate_telemetry.py — CAN Simulator Emitter.

Generates UAV telemetry based on a flight profile state machine and emits it via UDP
to simulate a CAN interface.

Flight Profile:
Land (Pre-flight) -> Takeoff -> High Altitude -> Low Altitude (30s) -> Land (Landing)

Usage:
    python -m src.utils.generate_telemetry --zone ior_maritime --fault-chance 0.4
"""

import argparse
import socket
import json
import time
import random
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

# Add project root to path if running directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from . import config
    from .utils import OUProcess, seed_from_flight_id, get_phase_at_time
    from ..core.environmental_model import EnvironmentalModel
except (ImportError, ValueError):
    from src.utils import config
    from src.utils.utils import OUProcess, seed_from_flight_id, get_phase_at_time
    from src.core.environmental_model import EnvironmentalModel

# UDP Configuration for simulated CAN interface
CAN_SIM_HOST = "127.0.0.1"
CAN_SIM_PORT = 5005

class FlightGenerator:
    """Generates telemetry based on a flight profile and emits it via UDP."""

    def __init__(
        self,
        flight_id: str = None,
        climate_zone: str = "ior_maritime",
        fault_chance: float = 0.0,
        airframe_id: str = config.DEFAULT_AIRFRAME_ID,
    ):
        self.flight_id = flight_id or f"FL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        self.climate_zone = climate_zone
        self.airframe_id = airframe_id

        # Seeded random number generator
        self.seed = seed_from_flight_id(self.flight_id)
        self.rng = random.Random(self.seed)

        # Mission setup
        self.start_time = datetime.now(timezone.utc)
        self.mission_time_s = 0.0

        # Fault setup
        self.fault_injected = None
        self.fault_start_s = None
        self.fault_severity = 0.0
        self._schedule_fault(fault_chance)

        # OU processes for smooth noise
        self.ou_processes: Dict[str, OUProcess] = {}
        self._init_ou_processes()

        # Environmental model
        self.env_model = EnvironmentalModel(
            climate_zone=climate_zone, airframe_id=airframe_id, rng=self.rng
        )

        print(f"CAN Simulator started for flight {self.flight_id}:")
        print(f"  Climate zone: {climate_zone}")
        print(f"  Airframe: {airframe_id}")
        print(f"  Fault injected: {self.fault_injected or 'None'}")
        print(f"  Emitting to {CAN_SIM_HOST}:{CAN_SIM_PORT}...")

    def _schedule_fault(self, fault_chance: float):
        if self.rng.random() < fault_chance:
            fault_type = self.rng.choice(list(config.FAULT_PROFILES.keys()))
            fault_profile = config.FAULT_PROFILES[fault_type]
            self.fault_injected = fault_profile["parameter"]
            self.fault_start_s = fault_profile["typical_start_s"] + self.rng.uniform(-300, 300)
            self.fault_severity = fault_profile["severity_per_s"]

    def _init_ou_processes(self):
        for param, nominal_value in config.EXPECTED_VALUES_NOMINAL.items():
            sigma = config.SENSOR_NOISE.get(param, 0.5)
            theta = config.OU_THETA.get(param, 0.1)
            self.ou_processes[param] = OUProcess(
                mean=nominal_value, theta=theta, sigma=sigma, x=nominal_value
            )

    def get_phase_altitude_and_temperature(self, mission_time_s: float) -> Tuple[float, float, str]:
        """
        Calculate altitude based on the new flight profile.
        Profile: Land -> Takeoff -> High -> Low (30s) -> Land
        """
        phase_name = get_phase_at_time(mission_time_s, config.MISSION_PHASES)
        phase_def = config.MISSION_PHASES.get(phase_name, {})

        if phase_name == "preflight":
            altitude_m = 100  # Ground level / idling
        elif phase_name == "takeoff":
            # Climb from 100m to 3000m
            phase_start = phase_def["start_s"]
            phase_duration = phase_def["duration_s"]
            progress = (mission_time_s - phase_start) / phase_duration
            altitude_m = 100 + (3000 - 100) * progress
        elif phase_name == "high_altitude":
            altitude_m = 3000
        elif phase_name == "low_altitude":
            # Dip from 3000m to 500m
            phase_start = phase_def["start_s"]
            phase_duration = phase_def["duration_s"]
            progress = (mission_time_s - phase_start) / phase_duration
            altitude_m = 3000 - (3000 - 500) * progress
        elif phase_name == "landing":
            # Descend from 500m to 0m
            phase_start = phase_def["start_s"]
            phase_duration = phase_def["duration_s"]
            progress = (mission_time_s - phase_start) / phase_duration
            altitude_m = 500 - 500 * progress
        else:
            altitude_m = 0

        # Ambient temperature decreases with altitude (~6.5°C/km)
        climate_def = config.CLIMATE_ZONES.get(self.climate_zone, {})
        base_temp = climate_def.get("temp_c_baseline", 15)
        lapse_rate = 0.0065
        ambient_temp_c = base_temp - (altitude_m * lapse_rate)

        return altitude_m, ambient_temp_c, phase_name

    def get_rpm_for_phase(self, mission_time_s: float) -> float:
        phase_name = get_phase_at_time(mission_time_s, config.MISSION_PHASES)
        phase_def = config.MISSION_PHASES.get(phase_name, {})
        target_rpm = phase_def.get("rpm_target", 2000)
        return max(500, target_rpm + self.rng.gauss(0, 50))

    def _get_phase_scaling(self, phase_name: str) -> Dict[str, float]:
        """Return scaling factors for parameters based on the flight phase."""
        scalings = {
            "preflight": {
                "rpm": 0.3, "cht_c": 0.6, "egt_c": 0.5, "oil_temp_c": 0.7,
                "oil_pressure_psi": 0.8, "fuel_flow_lph": 0.2, "vibration_g": 0.2, "afr": 1.1
            },
            "takeoff": {
                "rpm": 1.7, "cht_c": 1.2, "egt_c": 1.4, "oil_temp_c": 1.1,
                "oil_pressure_psi": 1.2, "fuel_flow_lph": 2.0, "vibration_g": 2.0, "afr": 0.8
            },
            "high_altitude": {
                "rpm": 1.0, "cht_c": 1.0, "egt_c": 1.0, "oil_temp_c": 1.0,
                "oil_pressure_psi": 1.0, "fuel_flow_lph": 1.0, "vibration_g": 1.0, "afr": 1.0
            },
            "low_altitude": {
                "rpm": 0.8, "cht_c": 0.9, "egt_c": 0.9, "oil_temp_c": 0.9,
                "oil_pressure_psi": 0.9, "fuel_flow_lph": 0.7, "vibration_g": 0.8, "afr": 1.0
            },
            "landing": {
                "rpm": 0.5, "cht_c": 0.8, "egt_c": 0.7, "oil_temp_c": 0.8,
                "oil_pressure_psi": 0.9, "fuel_flow_lph": 0.4, "vibration_g": 0.5, "afr": 1.1
            },
        }
        return scalings.get(phase_name, {k: 1.0 for k in config.EXPECTED_VALUES_NOMINAL})

    def generate_packet(self, mission_time_s: float) -> Dict:
        self.mission_time_s = mission_time_s
        altitude_m, ambient_temp_c, phase_name = self.get_phase_altitude_and_temperature(mission_time_s)

        # Get scaling for current phase
        scaling = self._get_phase_scaling(phase_name)

        dt = config.PACKET_INTERVAL_S

        # Update OU processes means based on phase
        ou_values = {}
        for param, ou in self.ou_processes.items():
            nominal = config.EXPECTED_VALUES_NOMINAL.get(param, 1.0)
            # Special case for RPM: use the phase's target RPM directly
            if param == "rpm":
                target = config.MISSION_PHASES.get(phase_name, {}).get("rpm_target", nominal)
                ou.mean = target
            else:
                ou.mean = nominal * scaling.get(param, 1.0)

            ou_values[param] = ou.step(dt=dt, rng=self.rng)

        climate_zone_def = config.CLIMATE_ZONES.get(self.climate_zone, {})
        env_packet = self.env_model.get_environmental_packet(
            altitude_m, climate_zone_def, phase_name, config.PACKET_INTERVAL_S
        )

        packet = {
            "flight_id": self.flight_id,
            "mission_time_s": mission_time_s,
            "timestamp": (self.start_time + timedelta(seconds=mission_time_s)).isoformat(),
            "phase": phase_name,
            "rpm": max(500, ou_values["rpm"]),
            "cht_c": max(0, ou_values["cht_c"]),
            "egt_c": max(0, ou_values["egt_c"]),
            "oil_temp_c": max(0, ou_values["oil_temp_c"]),
            "oil_pressure_psi": max(0, ou_values["oil_pressure_psi"]),
            "fuel_flow_lph": max(0, ou_values["fuel_flow_lph"]),
            "vibration_g": max(0, ou_values["vibration_g"]),
            "battery_v": max(10, ou_values["battery_v"]),
            "afr": max(10, ou_values["afr"]),
            "altitude_m": altitude_m,
            "ambient_temp_c": ambient_temp_c,
            "humidity_pct": env_packet["humidity_pct"],
            "pressure_altitude_m": env_packet["pressure_altitude_m"],
            "precipitation": env_packet["precipitation"],
            "hours_since_filter_service": env_packet["hours_since_filter_service"],
            "maritime_hours_cumulative": env_packet["maritime_hours_cumulative"],
            "climate_zone": self.climate_zone,
        }

        # Apply fault if active
        if self.fault_injected and self.fault_start_s <= mission_time_s:
            fault_elapsed = mission_time_s - self.fault_start_s
            fault_magnitude = self.fault_severity * fault_elapsed
            param = self.fault_injected
            packet[param] = max(0, packet[param] + fault_magnitude)

        return packet

    def run_flight(self):
        """Emit telemetry packets via UDP until the flight is complete."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        mission_time_s = 0.0
        packet_count = 0

        try:
            while mission_time_s < config.TOTAL_FLIGHT_DURATION_S:
                packet = self.generate_packet(mission_time_s)

                # Convert to JSON and send via UDP
                message = json.dumps(packet).encode('utf-8')
                sock.sendto(message, (CAN_SIM_HOST, CAN_SIM_PORT))

                packet_count += 1
                if packet_count % 10 == 0:
                    print(f"  [{packet_count}] Time: {mission_time_s/60:.1f}m | "
                          f"Phase: {packet['phase']} | Alt: {packet['altitude_m']:.0f}m | "
                          f"RPM: {packet['rpm']:.0f}")

                jitter = self.rng.uniform(-config.PACKET_INTERVAL_JITTER_S, config.PACKET_INTERVAL_JITTER_S)
                mission_time_s += config.PACKET_INTERVAL_S + jitter
                time.sleep(1.0)  # Simulation speed: 1s wall-clock per packet

            print(f"\nFlight cycle complete: {packet_count} packets emitted.")
        finally:
            sock.close()

def main():
    parser = argparse.ArgumentParser(description="CAN Simulator Telemetry Emitter")
    parser.add_argument("--flight-id", help="Manual flight ID (auto-generated if omitted)")
    parser.add_argument("--zone", default="ior_maritime", choices=list(config.CLIMATE_ZONES.keys()))
    parser.add_argument("--fault-chance", type=float, default=0.0)
    parser.add_argument("--airframe-id", default=config.DEFAULT_AIRFRAME_ID)

    args = parser.parse_args()

    generator = FlightGenerator(
        flight_id=args.flight_id,
        climate_zone=args.zone,
        fault_chance=args.fault_chance,
        airframe_id=args.airframe_id,
    )
    generator.run_flight()

if __name__ == "__main__":
    main()
