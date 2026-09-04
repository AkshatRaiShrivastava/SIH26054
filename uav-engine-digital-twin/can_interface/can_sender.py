"""SocketCAN sender with YAML-driven CAN mapping."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import yaml

from simulator.telemetry import EngineTelemetry


@dataclass(frozen=True)
class SignalMapping:
    name: str
    can_id: int
    unit: str
    scale: float
    offset: float = 0.0
    byte_order: str = "big"
    dtype: str = "uint16"


class CANMapping:
    def __init__(self, mappings: Dict[str, SignalMapping]) -> None:
        self.mappings = mappings

    @classmethod
    def load(cls, path: str | Path) -> "CANMapping":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        signals = raw.get("signals", {})
        mappings: Dict[str, SignalMapping] = {}
        for name, item in signals.items():
            mappings[name] = SignalMapping(
                name=name,
                can_id=int(item["can_id"]),
                unit=str(item.get("unit", "")),
                scale=float(item.get("scale", 1.0)),
                offset=float(item.get("offset", 0.0)),
                byte_order=str(item.get("byte_order", "big")),
                dtype=str(item.get("dtype", "uint16")),
            )
        return cls(mappings)

    def items(self) -> Iterable[Tuple[str, SignalMapping]]:
        return self.mappings.items()


class CANEncoder:
    def __init__(self, mapping: CANMapping) -> None:
        self.mapping = mapping

    @staticmethod
    def encode_value(value: float, scale: float, offset: float = 0.0) -> bytes:
        raw = int(round((value - offset) / scale))
        raw = max(0, min(65535, raw))
        return raw.to_bytes(2, byteorder="big", signed=False)

    @staticmethod
    def decode_value(payload: bytes, scale: float, offset: float = 0.0) -> float:
        raw = int.from_bytes(payload[:2], byteorder="big", signed=False)
        return raw * scale + offset

    def encode_telemetry(self, telemetry: EngineTelemetry) -> Dict[int, bytes]:
        values = telemetry.as_dict()
        frames: Dict[int, bytes] = {}
        for name, mapping in self.mapping.items():
            if name not in values:
                raise KeyError(f"Telemetry missing field: {name}")
            frames[mapping.can_id] = self.encode_value(values[name], mapping.scale, mapping.offset)
        return frames

    def decode_frames(self, frames: Dict[int, bytes]) -> Dict[str, float]:
        decoded: Dict[str, float] = {}
        for name, mapping in self.mapping.items():
            if mapping.can_id in frames:
                decoded[name] = self.decode_value(frames[mapping.can_id], mapping.scale, mapping.offset)
        return decoded


class CANSender:
    def __init__(self, channel: str, mapping: CANMapping) -> None:
        self.channel = channel
        self.mapping = mapping
        self.encoder = CANEncoder(mapping)
        self._bus = None

    def _ensure_bus(self):
        if self._bus is None:
            import can  # type: ignore

            self._bus = can.Bus(interface="socketcan", channel=self.channel)
        return self._bus

    def send(self, telemetry: EngineTelemetry) -> None:
        try:
            bus = self._ensure_bus()
            import can  # type: ignore

            for can_id, payload in self.encoder.encode_telemetry(telemetry).items():
                msg = can.Message(arbitration_id=can_id, data=payload, is_extended_id=False)
                bus.send(msg)
        except Exception:
            # Re-raise after preserving the root cause; do not silently ignore CAN errors.
            raise

    def close(self) -> None:
        """Release the SocketCAN bus so python-can does not emit shutdown warnings."""
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None
