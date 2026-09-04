"""CAN decoder using a YAML mapping file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml


@dataclass(frozen=True)
class SignalMapping:
    name: str
    can_id: int
    unit: str
    scale: float
    offset: float = 0.0
    byte_order: str = "big"
    dtype: str = "uint16"
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class CANMapping:
    def __init__(self, mappings: Dict[int, SignalMapping]) -> None:
        self.mappings = mappings

    @classmethod
    def load(cls, path: str | Path) -> "CANMapping":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        signals = payload.get("signals", {})
        mappings: Dict[int, SignalMapping] = {}
        for name, data in signals.items():
            mapping = SignalMapping(
                name=name,
                can_id=int(data["can_id"]),
                unit=str(data.get("unit", "")),
                scale=float(data.get("scale", 1.0)),
                offset=float(data.get("offset", 0.0)),
                byte_order=str(data.get("byte_order", "big")),
                dtype=str(data.get("dtype", "uint16")),
                min_value=data.get("min"),
                max_value=data.get("max"),
            )
            mappings[mapping.can_id] = mapping
        return cls(mappings)


class CANDecoder:
    def __init__(self, mapping: CANMapping) -> None:
        self.mapping = mapping

    @staticmethod
    def decode_raw(payload: bytes, scale: float, offset: float = 0.0) -> float:
        raw = int.from_bytes(payload[:2], byteorder="big", signed=False)
        return raw * scale + offset

    def decode(self, message) -> Optional[tuple[str, float]]:
        mapping = self.mapping.mappings.get(int(message.arbitration_id))
        if mapping is None:
            return None
        value = self.decode_raw(bytes(message.data), mapping.scale, mapping.offset)
        return mapping.name, value
