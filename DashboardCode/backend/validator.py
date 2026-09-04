"""Telemetry validator for decoded CAN values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .can_decoder import SignalMapping


@dataclass
class ValidationResult:
    valid: bool
    value: float
    reason: Optional[str] = None


class TelemetryValidator:
    def validate(self, mapping: SignalMapping, value: float) -> ValidationResult:
        if mapping.min_value is not None and value < float(mapping.min_value):
            return ValidationResult(False, value, f"below minimum {mapping.min_value}")
        if mapping.max_value is not None and value > float(mapping.max_value):
            return ValidationResult(False, value, f"above maximum {mapping.max_value}")
        return ValidationResult(True, value)
