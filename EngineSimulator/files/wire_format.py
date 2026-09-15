"""Shared encrypted CAN wire format for FADEC and backend."""

import os
import struct
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TELEMETRY_CAN_ID = 0x100
HEARTBEAT_CAN_ID = 0x101
FAULT_CAN_ID = 0x102
PAYLOAD_FORMAT = "!d f f f f f f f f f B I"
PAYLOAD_SIZE = struct.calcsize(PAYLOAD_FORMAT)
NONCE_SIZE = 12
TAG_SIZE = 16
FAULT_CHANNELS = (
    "cht_c", "oil_temp_c", "oil_pressure_psi", "egt_c", "fuel_flow_lph", "vibration_g"
)
STAGE_IDS = {
    "START_WARMUP": 1, "GROUND_IDLE_TAXI": 2, "TAKEOFF": 3, "CLIMB": 4,
    "CRUISE_TRANSIT": 5, "LOITER_ISR": 6, "DESCENT": 7,
    "APPROACH_LANDING": 8, "SHUTDOWN_COOLDOWN": 9,
    "GROUND_IDLE": 10, "TAXI": 11, "CRUISE_LOITER": 12, "LANDING": 13, "SHUTDOWN": 14,
}
STAGE_NAMES = {value: key for key, value in STAGE_IDS.items()}


def key_from_environment(value: str | None = None) -> bytes:
    raw = value or os.environ.get("FADEC_CAN_KEY")
    if not raw:
        raise ValueError("FADEC_CAN_KEY must contain a 32-byte key in hex or base64")
    try:
        key = bytes.fromhex(raw)
    except ValueError:
        import base64
        try:
            key = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError("FADEC_CAN_KEY must be 64 hex characters or base64") from exc
    if len(key) != 32:
        raise ValueError("FADEC_CAN_KEY must decode to exactly 32 bytes")
    return key


def encrypt_payload(payload: bytes, key: bytes) -> bytes:
    nonce = os.urandom(NONCE_SIZE)
    return nonce + AESGCM(key).encrypt(nonce, payload, None)


def decrypt_payload(message: bytes, key: bytes) -> bytes:
    if len(message) < NONCE_SIZE + TAG_SIZE:
        raise ValueError("encrypted CAN message is too short")
    return AESGCM(key).decrypt(message[:NONCE_SIZE], message[NONCE_SIZE:], None)


def fault_bitmask(active_faults: list[str] | tuple[str, ...]) -> int:
    return sum(1 << FAULT_CHANNELS.index(channel) for channel in active_faults if channel in FAULT_CHANNELS)


def pack_telemetry(row: dict[str, Any]) -> bytes:
    return struct.pack(
        PAYLOAD_FORMAT,
        float(row["time_s"]), float(row["rpm"]), float(row["altitude_m"]),
        float(row["ambient_temp_c"]), float(row["actual_cht_c"]), float(row["actual_oil_temp_c"]),
        float(row["actual_oil_pressure_psi"]), float(row["actual_egt_c"]),
        float(row["actual_fuel_flow_lph"]), float(row["actual_vibration_g"]),
        STAGE_IDS.get(row["stage"], 0), fault_bitmask(row.get("active_faults", [])),
    )


def unpack_telemetry(payload: bytes) -> dict[str, Any]:
    if len(payload) != PAYLOAD_SIZE:
        raise ValueError(f"telemetry payload must be {PAYLOAD_SIZE} bytes")
    values = struct.unpack(PAYLOAD_FORMAT, payload)
    return {
        "timestamp_s": values[0], "rpm": values[1], "altitude_m": values[2],
        "ambient_temp_c": values[3], "cht_c": values[4], "oil_temp_c": values[5],
        "oil_pressure_psi": values[6], "egt_c": values[7], "fuel_flow_lph": values[8],
        "vibration_g": values[9], "stage_id": values[10],
        "stage": STAGE_NAMES.get(values[10], f"UNKNOWN_{values[10]}"),
        "active_fault_bitmask": values[11],
        "active_faults": [channel for index, channel in enumerate(FAULT_CHANNELS) if values[11] & (1 << index)],
    }


def fragment(message: bytes, max_data_bytes: int = 8) -> list[bytes]:
    chunk_size = max_data_bytes - 1
    chunks = [message[offset:offset + chunk_size] for offset in range(0, len(message), chunk_size)]
    if len(chunks) > 15:
        raise ValueError("message is too large for the classic CAN fragment header")
    return [bytes([0x10 | len(chunks)]) + chunks[0]] + [bytes([0x20 | index]) + chunk for index, chunk in enumerate(chunks[1:], 1)]


def defragment(frames: list[bytes]) -> bytes:
    if not frames or frames[0][0] & 0xF0 != 0x10:
        raise ValueError("missing CAN first fragment")
    expected = frames[0][0] & 0x0F
    if expected != len(frames):
        raise ValueError("incomplete CAN message")
    chunks = [frames[0][1:]]
    for index, frame in enumerate(frames[1:], 1):
        if frame[0] != 0x20 | index:
            raise ValueError("out-of-order CAN fragment")
        chunks.append(frame[1:])
    return b"".join(chunks)
