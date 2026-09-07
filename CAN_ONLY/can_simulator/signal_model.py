import random
import math
import time
from .config import RPM_MIN, RPM_MAX, THROTTLE_MIN, THROTTLE_MAX

class EngineTelemetryModel:
    """
    Generates correlated synthetic UAV engine telemetry based on physical approximations.
    """
    def __init__(self):
        # Initial State
        self.throttle = 0.0
        self.rpm = 0.0
        self.engine_load = 0.0
        self.cht = 20.0
        self.egt = 20.0
        self.oil_pressure = 0.0
        self.oil_temp = 20.0
        self.fuel_flow = 0.0
        self.fuel_pressure = 300.0
        self.afr = 14.7
        self.vibration = 0.0
        self.battery_voltage = 12.4
        self.alternator_voltage = 12.4
        self.altitude = 0.0
        self.ambient_temp = 15.0

        self.health_penalty = 0.0 # Simulates engine wear/faults
        self.time_elapsed = 0.0

    def update(self, dt=0.1):
        """
        Updates the telemetry state based on correlations and first-order lags.
        """
        self.time_elapsed += dt

        # 1. Simulate a dynamic throttle (slowly drifting)
        # Every few seconds, change the target throttle slightly
        if random.random() < 0.05:
            self.throttle = max(THROTTLE_MIN, min(THROTTLE_MAX, self.throttle + random.uniform(-10, 10)))

        # 2. RPM and Engine Load
        # Target RPM is proportional to throttle
        target_rpm = (self.throttle / THROTTLE_MAX) * RPM_MAX * 0.8 + 1000 # Idle ~1000
        if self.throttle == 0:
            target_rpm = 0

        # RPM first order lag
        self.rpm = self.rpm * 0.9 + target_rpm * 0.1
        self.engine_load = (self.rpm / RPM_MAX) * 100.0 * (self.throttle / THROTTLE_MAX if self.throttle > 0 else 0)

        # 3. Temperatures
        # CHT: depends on RPM and Altitude
        self.cht = self.cht * 0.98 + (60.0 + self.rpm * 0.016 + self.altitude * 0.006 + 8.0 * self.health_penalty) * 0.02

        # EGT: depends on RPM
        self.egt = self.egt * 0.98 + (500.0 + self.rpm * 0.05 + self.health_penalty * 2.0) * 0.02

        # Oil Temp: depends on RPM and Load
        self.oil_temp = self.oil_temp * 0.99 + (72.0 + self.rpm * 0.005 + self.engine_load * 0.18) * 0.01

        # 4. Lubrication
        # Oil Pressure: increases with RPM, decreases with Oil Temp
        # Simple approx: base + rpm_term - temp_term
        target_oil_pressure = 380.0 + (3500 - self.rpm) * 0.04 + self.engine_load * 0.6
        self.oil_pressure = self.oil_pressure * 0.9 + target_oil_pressure * 0.1

        # 5. Fuel
        # Fuel Flow: proportional to RPM and Load
        self.fuel_flow = (self.rpm / RPM_MAX) * 60.0 + (self.engine_load / 100.0) * 10.0
        self.fuel_pressure = 300.0 + random.uniform(-2, 2)
        self.afr = 14.7 + (35.0 - self.rpm * 0.0015) * 0.02

        # 6. Vibration
        # Vibration: increases with RPM and EGT deviation from 'sweet spot'
        target_vib = 1.2 + self.rpm * 0.00035 + abs(self.egt - 650.0) * 0.002 + self.health_penalty
        self.vibration = self.vibration * 0.9 + target_vib * 0.1

        # 7. Electrical
        # Battery Voltage: 12.4V when off, ~14V when alternator is charging (RPM > 1000)
        if self.rpm > 1000:
            self.alternator_voltage = 14.1 + (self.rpm / RPM_MAX) * 0.5 + random.uniform(-0.1, 0.1)
            self.battery_voltage = self.battery_voltage * 0.99 + self.alternator_voltage * 0.01
        else:
            self.alternator_voltage = 0.0
            self.battery_voltage = self.battery_voltage * 0.999 + 12.4 * 0.001

        # 8. Environment
        # Altitude: slow climb/descend
        self.altitude += random.uniform(-1, 1) * 10.0
        self.altitude = max(0, min(12000, self.altitude))

        # Ambient Temp: decreases with altitude (lapse rate ~6.5C per 1000m)
        self.ambient_temp = 15.0 - (self.altitude / 1000.0) * 6.5 + random.uniform(-0.5, 0.5)

    def get_telemetry(self):
        """
        Returns current telemetry as a dictionary for DBC encoding.
        """
        return {
            'RPM': int(self.rpm),
            'EngineLoad': int(self.engine_load),
            'Throttle': int(self.throttle),
            'CHT': round(self.cht, 2),
            'EGT': round(self.egt, 2),
            'OilPressure': round(self.oil_pressure, 2),
            'OilTemperature': round(self.oil_temp, 2),
            'FuelFlow': round(self.fuel_flow, 2),
            'FuelPressure': round(self.fuel_pressure, 2),
            'AFR': round(self.afr, 2),
            'EngineVibration': round(self.vibration, 2),
            'BatteryVoltage': round(self.battery_voltage, 2),
            'AlternatorVoltage': round(self.alternator_voltage, 2),
            'Altitude': int(self.altitude),
            'AmbientTemperature': round(self.ambient_temp, 2),
        }
