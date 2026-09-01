"""
STEP 3: Environmental fields for generate_telemetry.py

This module extends the basic telemetry generator with:
- Humidity profiles (climate-zone dependent)
- Pressure altitude calculation
- Precipitation events
- Dust exposure tracking
- Maritime corrosion tracking
"""

import random
from datetime import timedelta


class EnvironmentalModel:
    """Generates environmental parameters for a flight."""

    def __init__(self, climate_zone: str, airframe_id: str, rng: random.Random):
        """
        Initialize environmental model.

        Args:
            climate_zone: one of the climate zone keys from config
            airframe_id: persistent airframe identifier
            rng: seeded random.Random instance
        """
        self.climate_zone = climate_zone
        self.airframe_id = airframe_id
        self.rng = rng

        # Cross-flight persistent state (would normally come from DB)
        self.hours_since_filter_service = 100.0
        self.maritime_hours_cumulative = 50.0

        # In-flight accumulation
        self.flight_hours_accumulated = 0.0

    def get_humidity_profile(self, altitude_m: float, base_humidity: float) -> float:
        """
        Generate humidity based on altitude and climate zone.

        Args:
            altitude_m: current altitude (m)
            base_humidity: baseline humidity for the zone

        Returns:
            relative humidity (%)
        """
        # Humidity decreases with altitude (roughly 2% per 300m)
        altitude_factor = altitude_m / 300.0 * 2.0
        adjusted_humidity = max(5, base_humidity - altitude_factor)

        # Add smooth variation
        noise = self.rng.gauss(0, 3)
        humidity_pct = min(100, max(5, adjusted_humidity + noise))

        return humidity_pct

    def get_pressure_altitude(self, geometric_altitude_m: float) -> float:
        """
        Compute pressure altitude (approximation).

        For simplicity, assuming standard atmosphere conditions.
        Pressure altitude ≈ geometric altitude (small correction for weather).

        Args:
            geometric_altitude_m: altitude in meters

        Returns:
            pressure altitude in meters
        """
        # Add small weather-induced variation (±5% typically)
        weather_factor = self.rng.gauss(1.0, 0.05)
        pressure_alt = geometric_altitude_m * weather_factor
        return pressure_alt

    def should_precipitation_event(self, climate_zone: str) -> bool:
        """
        Determine if precipitation is occurring.

        Monsoon belt and maritime zones have higher precipitation probability.

        Args:
            climate_zone: climate zone name

        Returns:
            True if precipitation event is active
        """
        precipitation_rates = {
            "himalayan": 0.05,
            "desert": 0.01,
            "ior_maritime": 0.15,
            "monsoon_belt": 0.25,
        }

        rate = precipitation_rates.get(climate_zone, 0.1)
        return self.rng.random() < rate

    def accumulate_dust_exposure(self, dt_hours: float):
        """
        Accumulate dust exposure over flight time.

        Args:
            dt_hours: time increment (hours)
        """
        self.flight_hours_accumulated += dt_hours
        # Filter service hours accumulate based on zone's dust load
        zone_factors = {
            "himalayan": 0.1,
            "desert": 0.8,
            "ior_maritime": 0.2,
            "monsoon_belt": 0.3,
        }
        zone_factor = zone_factors.get(self.climate_zone, 0.2)
        self.hours_since_filter_service += dt_hours * zone_factor

    def accumulate_maritime_exposure(self, dt_hours: float):
        """
        Accumulate maritime corrosion exposure.

        Args:
            dt_hours: time increment (hours)
        """
        if self.climate_zone == "ior_maritime":
            self.maritime_hours_cumulative += dt_hours

    def get_environmental_packet(
        self,
        altitude_m: float,
        climate_zone_def: dict,
        phase: str,
        dt_packet_s: float,
    ) -> dict:
        """
        Generate environmental fields for a telemetry packet.

        Args:
            altitude_m: current altitude (m)
            climate_zone_def: climate zone definition dict from config
            phase: mission phase name
            dt_packet_s: time since last packet (seconds)

        Returns:
            dict with environmental fields
        """
        # Accumulate exposure times
        dt_hours = dt_packet_s / 3600.0
        self.accumulate_dust_exposure(dt_hours)
        self.accumulate_maritime_exposure(dt_hours)

        # Humidity
        base_humidity = climate_zone_def.get("humidity_pct_baseline", 50)
        humidity_pct = self.get_humidity_profile(altitude_m, base_humidity)

        # Pressure altitude
        pressure_altitude_m = self.get_pressure_altitude(altitude_m)

        # Precipitation
        precipitation = 1 if self.should_precipitation_event(self.climate_zone) else 0

        return {
            "humidity_pct": humidity_pct,
            "pressure_altitude_m": pressure_altitude_m,
            "precipitation": precipitation,
            "hours_since_filter_service": self.hours_since_filter_service,
            "maritime_hours_cumulative": self.maritime_hours_cumulative,
        }


if __name__ == "__main__":
    import config

    # Test environmental model
    rng = random.Random(12345)
    env = EnvironmentalModel("ior_maritime", "AIRFRAME-001", rng)

    zone_def = config.CLIMATE_ZONES["ior_maritime"]

    print("Environmental Model Test")
    print("=" * 60)

    for altitude in [0, 1000, 2000, 3000]:
        packet = env.get_environmental_packet(altitude, zone_def, "cruise", 2.5)
        print(f"Altitude: {altitude:4d}m | Humidity: {packet['humidity_pct']:5.1f}% | "
              f"Precip: {packet['precipitation']} | "
              f"Filter hours: {packet['hours_since_filter_service']:.1f}")
