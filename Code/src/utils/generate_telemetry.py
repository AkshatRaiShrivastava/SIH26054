"""
generate_telemetry.py — STEP 1: Engine-only telemetry generation with seeded reproducibility.

Generates a complete flight's telemetry packets with:
- Seeded reproducibility (same flight_id → identical output)
- Smooth OU processes for sensor noise
- Scheduled fault injection
- Immediate database writes (not buffered)

Usage:
    python -m src.utils.generate_telemetry --flight-id FL-2026-08-30-001 --zone ior_maritime --fault-chance 0.4
"""

import argparse
import sqlite3
import time
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

# Add project root to path if running directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    # Try relative imports first (when run as module)
    from . import config
    from ..database.database import get_connection, close_connection
    from .utils import OUProcess, seed_from_flight_id, get_phase_at_time
    from ..core.environmental_model import EnvironmentalModel
except (ImportError, ValueError):
    # Fall back to absolute imports (when run directly)
    from src.utils import config
    from src.database.database import get_connection, close_connection
    from src.utils.utils import OUProcess, seed_from_flight_id, get_phase_at_time
    from src.core.environmental_model import EnvironmentalModel


class FlightGenerator:
    """Generates a single flight's worth of telemetry packets."""

    def __init__(
        self,
        flight_id: str,
        climate_zone: str = "ior_maritime",
        fault_chance: float = 0.0,
        airframe_id: str = config.DEFAULT_AIRFRAME_ID,
    ):
        """
        Initialize flight generator.

        Args:
            flight_id: unique flight identifier
            climate_zone: climate zone for this flight
            fault_chance: probability of fault injection (0.0 to 1.0)
            airframe_id: persistent airframe/tail number
        """
        self.flight_id = flight_id
        self.climate_zone = climate_zone
        self.airframe_id = airframe_id

        # Seeded random number generator
        self.seed = seed_from_flight_id(flight_id)
        self.rng = random.Random(self.seed)

        # Mission setup
        self.start_time = datetime.utcnow()
        self.mission_time_s = 0.0

        # Fault setup (scheduled once at start, not per-packet)
        self.fault_injected = None
        self.fault_start_s = None
        self.fault_severity = 0.0
        self._schedule_fault(fault_chance)

        # OU processes for each engine parameter
        self.ou_processes: Dict[str, OUProcess] = {}
        self._init_ou_processes()

        # Environmental model
        climate_zone_def = config.CLIMATE_ZONES.get(climate_zone, {})
        self.env_model = EnvironmentalModel(
            climate_zone=climate_zone, airframe_id=airframe_id, rng=self.rng
        )

        print(f"Flight {flight_id} initialized:")
        print(f"  Seed: {self.seed}")
        print(f"  Climate zone: {climate_zone}")
        print(f"  Airframe: {airframe_id}")
        print(f"  Fault injected: {self.fault_injected or 'None'}")

    def _schedule_fault(self, fault_chance: float):
        """Schedule fault injection (once per flight)."""
        if self.rng.random() < fault_chance:
            # Choose a fault type
            fault_type = self.rng.choice(list(config.FAULT_PROFILES.keys()))
            fault_profile = config.FAULT_PROFILES[fault_type]

            self.fault_injected = fault_profile["parameter"]
            self.fault_start_s = fault_profile["typical_start_s"] + self.rng.uniform(
                -300, 300
            )  # ±5 min jitter
            self.fault_severity = fault_profile["severity_per_s"]

    def _init_ou_processes(self):
        """Initialize OU processes for smooth noise on each parameter."""
        for param, nominal_value in config.EXPECTED_VALUES_NOMINAL.items():
            sigma = config.SENSOR_NOISE.get(param, 0.5)
            theta = config.OU_THETA.get(param, 0.1)

            self.ou_processes[param] = OUProcess(
                mean=nominal_value, theta=theta, sigma=sigma, x=nominal_value
            )

    def get_phase_altitude_and_temperature(self, mission_time_s: float) -> tuple:
        """
        Get altitude and ambient temperature for current mission phase.
        Returns (altitude_m, ambient_temp_c, phase_name)
        """
        phase_name = get_phase_at_time(mission_time_s, config.MISSION_PHASES)
        phase_def = config.MISSION_PHASES.get(phase_name, {})

        # Altitude profile: climb to 3000m during climb phase
        if phase_name == "preflight":
            altitude_m = 100
        elif phase_name == "takeoff":
            # Climb from 100m to 1000m
            phase_start = phase_def["start_s"]
            phase_duration = phase_def["duration_s"]
            progress = (mission_time_s - phase_start) / phase_duration
            altitude_m = 100 + (1000 - 100) * progress
        elif phase_name == "climb":
            # Climb from 1000m to 3000m
            phase_start = phase_def["start_s"]
            phase_duration = phase_def["duration_s"]
            progress = (mission_time_s - phase_start) / phase_duration
            altitude_m = 1000 + (3000 - 1000) * progress
        elif phase_name == "cruise":
            altitude_m = 3000
        elif phase_name == "descent":
            # Descend from 3000m to 500m
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

        # Ambient temperature profile: decreases with altitude
        # Lapse rate: ~6.5°C/km
        climate_def = config.CLIMATE_ZONES.get(self.climate_zone, {})
        base_temp = climate_def.get("temp_c_baseline", 15)
        lapse_rate = 0.0065  # °C/m
        ambient_temp_c = base_temp - (altitude_m * lapse_rate)

        return altitude_m, ambient_temp_c, phase_name

    def get_rpm_for_phase(self, mission_time_s: float) -> float:
        """Get target RPM for current phase with minor random variation."""
        phase_name = get_phase_at_time(mission_time_s, config.MISSION_PHASES)
        phase_def = config.MISSION_PHASES.get(phase_name, {})
        target_rpm = phase_def.get("rpm_target", 2000)

        # Add smooth variation around target
        rpm_variation = self.rng.gauss(0, 50)
        return max(500, target_rpm + rpm_variation)

    def generate_packet(self, mission_time_s: float) -> Dict:
        """
        Generate a single telemetry packet at the given mission time.

        Returns:
            dict with all telemetry fields
        """
        self.mission_time_s = mission_time_s

        # Compute current phase and altitude
        altitude_m, ambient_temp_c, phase_name = self.get_phase_altitude_and_temperature(
            mission_time_s
        )

        # Get RPM for this phase
        rpm = self.get_rpm_for_phase(mission_time_s)

        # Update all OU processes for smooth noise
        dt = config.PACKET_INTERVAL_S  # time step
        ou_values = {}
        for param, ou_process in self.ou_processes.items():
            ou_values[param] = ou_process.step(dt=dt, rng=self.rng)

        # Generate environmental fields
        climate_zone_def = config.CLIMATE_ZONES.get(self.climate_zone, {})
        env_packet = self.env_model.get_environmental_packet(
            altitude_m, climate_zone_def, phase_name, config.PACKET_INTERVAL_S
        )

        # Build packet
        packet = {
            "flight_id": self.flight_id,
            "mission_time_s": mission_time_s,
            "timestamp": (self.start_time + timedelta(seconds=mission_time_s)).isoformat(),
            "phase": phase_name,
            # Engine channels (from OU processes, adjusted by phase)
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
            # Environmental channels (from environmental model)
            "humidity_pct": env_packet["humidity_pct"],
            "pressure_altitude_m": env_packet["pressure_altitude_m"],
            "precipitation": env_packet["precipitation"],
            "hours_since_filter_service": env_packet["hours_since_filter_service"],
            "maritime_hours_cumulative": env_packet["maritime_hours_cumulative"],
            "climate_zone": self.climate_zone,
        }

        # Apply fault if scheduled and active
        if (
            self.fault_injected
            and self.fault_start_s <= mission_time_s
            and mission_time_s < config.TOTAL_FLIGHT_DURATION_S
        ):
            # Monotonic fault trend
            fault_elapsed = mission_time_s - self.fault_start_s
            fault_magnitude = self.fault_severity * fault_elapsed

            param = self.fault_injected
            current_value = packet[param]

            # Apply fault with bounds checking
            if "pressure" in param or "flow" in param:
                # These decrease
                packet[param] = max(0, current_value + fault_magnitude)
            else:
                # These increase (temp, vibration)
                packet[param] = max(0, current_value + fault_magnitude)

        return packet

    def run_flight(self, db_path: str = "digital_twin.db"):
        """
        Run a complete flight: generate packets and write to database immediately.

        Args:
            db_path: path to SQLite database
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Insert a row into `flights`.
            cursor.execute(
                """
                INSERT INTO flights (flight_id, start_time, climate_zone, seed, fault_injected, status, airframe_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    self.flight_id,
                    self.start_time.isoformat(),
                    self.climate_zone,
                    self.seed,
                    self.fault_injected,
                    "in_progress",
                    self.airframe_id,
                ),
            )
            conn.commit()
            print(f"Flight record created: {self.flight_id}")

            # Generate and write packets
            mission_time_s = 0.0
            packet_count = 0

            while mission_time_s < config.TOTAL_FLIGHT_DURATION_S:
                # Generate packet
                packet = self.generate_packet(mission_time_s)

                # Write to database immediately
                cursor.execute(
                    """
                    INSERT INTO telemetry (
                        flight_id, mission_time_s, timestamp, phase,
                        rpm, cht_c, egt_c, oil_temp_c, oil_pressure_psi,
                        fuel_flow_lph, vibration_g, battery_v, afr,
                        altitude_m, ambient_temp_c,
                        humidity_pct, pressure_altitude_m, precipitation,
                        hours_since_filter_service, maritime_hours_cumulative,
                        climate_zone
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?)
                """,
                    (
                        packet["flight_id"],
                        packet["mission_time_s"],
                        packet["timestamp"],
                        packet["phase"],
                        packet["rpm"],
                        packet["cht_c"],
                        packet["egt_c"],
                        packet["oil_temp_c"],
                        packet["oil_pressure_psi"],
                        packet["fuel_flow_lph"],
                        packet["vibration_g"],
                        packet["battery_v"],
                        packet["afr"],
                        packet["altitude_m"],
                        packet["ambient_temp_c"],
                        packet["humidity_pct"],
                        packet["pressure_altitude_m"],
                        packet["precipitation"],
                        packet["hours_since_filter_service"],
                        packet["maritime_hours_cumulative"],
                        packet["climate_zone"],
                    ),
                )
                conn.commit()

                packet_count += 1
                if packet_count % 10 == 0:
                    print(
                        f"  [{packet_count}] Mission time: {mission_time_s/60:.1f} min, "
                        f"RPM: {packet['rpm']:.0f}, CHT: {packet['cht_c']:.1f}°C, "
                        f"Phase: {packet['phase']}"
                    )

                # Advance time with small jitter for realism
                jitter = self.rng.uniform(
                    -config.PACKET_INTERVAL_JITTER_S, config.PACKET_INTERVAL_JITTER_S
                )
                mission_time_s += config.PACKET_INTERVAL_S + jitter

                # Simulate packet pacing (2-3 s between packets)
                time.sleep(0.1)  # Short sleep to allow concurrent reads

            # Mark flight complete
            cursor.execute(
                "UPDATE flights SET status = 'complete' WHERE flight_id = ?",
                (self.flight_id,),
            )
            conn.commit()

            print(f"\nFlight complete: {packet_count} packets written")
            print(f"Database: {db_path}")

        finally:
            close_connection(conn)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate telemetry for a single UAV flight."
    )
    parser.add_argument("--flight-id", required=True, help="Flight identifier (e.g., FL-2026-08-30-001)")
    parser.add_argument(
        "--zone",
        default="ior_maritime",
        choices=list(config.CLIMATE_ZONES.keys()),
        help="Climate zone for this flight",
    )
    parser.add_argument(
        "--fault-chance",
        type=float,
        default=0.0,
        help="Probability of fault injection (0.0 to 1.0)",
    )
    parser.add_argument(
        "--airframe-id",
        default=config.DEFAULT_AIRFRAME_ID,
        help="Airframe/tail number (for cross-flight tracking)",
    )

    args = parser.parse_args()

    # Generate flight
    generator = FlightGenerator(
        flight_id=args.flight_id,
        climate_zone=args.zone,
        fault_chance=args.fault_chance,
        airframe_id=args.airframe_id,
    )

    generator.run_flight()


if __name__ == "__main__":
    main()
