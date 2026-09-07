from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MissionStartRequest(BaseModel):
    scenario: str = "normal"
    speed_multiplier: float = 1.0
    phase_durations_s: Dict[int, float] = Field(default_factory=dict)


class TelemetryRecord(BaseModel):
    mission_id: str
    timestamp: Optional[str] = None
    elapsed_s: float
    phase_id: int
    rpm: float
    cht_c: float
    egt_c: float
    oil_pressure_kpa: float
    oil_temperature_c: float
    fuel_flow_lph: float
    vibration_mms: float
    afr: float
    battery_voltage: float
    altitude_m: float
    ambient_temp_c: float


class ComputedMetrics(BaseModel):
    mission_id: str
    timestamp: Optional[str] = None
    elapsed_s: float
    phase_id: int
    cht_expected: float
    cht_deviation_pct: float
    egt_expected: float
    egt_deviation_pct: float
    oil_pressure_expected: float
    oil_pressure_deviation_pct: float
    oil_temp_expected: float
    oil_temp_deviation_pct: float
    fuel_flow_expected: float
    fuel_flow_deviation_pct: float
    vibration_baseline: float
    vibration_deviation_pct: float
    anomaly_score: float
    is_anomaly: bool
    model_version: str = "prototype"
    health_index: float


class FaultEvent(BaseModel):
    mission_id: str
    timestamp: Optional[str] = None
    elapsed_s: float
    fault_category: str
    confidence: str
    driving_features: List[str]


class RULPrediction(BaseModel):
    mission_id: str
    timestamp: Optional[str] = None
    elapsed_s: float
    predicted_rul_minutes: float
    confidence_band_minutes: float
    driving_channel: str
    model_version: str


class LiveSocketPayload(BaseModel):
    channel: str = "live"
    mission_id: str
    elapsed_s: float
    phase_id: int
    raw: Dict[str, float]
    computed: Dict[str, Any]
    physics: Dict[str, Any]
    fault_alert: Optional[Dict[str, Any]] = None
    rul: Optional[Dict[str, Any]] = None
