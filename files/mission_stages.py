"""
mission_stages.py
==================
Defines the fixed mission-stage sequence for a MALE UAV ISR sortie, and the
selectable environmental presets. Stage ORDER is fixed (a real flight always
goes idle -> taxi -> takeoff -> climb -> cruise -> descent -> landing ->
shutdown); stage DURATION and the environmental preset are what the operator
configures at the start of a simulation run.
"""

# Fixed stage sequence. rpm/throttle/afr are TARGET (steady-state) values the
# simulator ramps toward during each stage; altitude_frac says how far
# through the ground<->cruise altitude range this stage's target altitude
# sits (0 = airfield elevation, 1 = configured cruise altitude).
STAGE_DEFINITIONS = [
    # name,              rpm,   throttle, afr_nominal, altitude_frac, default_duration_s
    ("GROUND_IDLE",       1400, 0.08,     14.7,        0.00,  120),
    ("TAXI",              1800, 0.15,     14.7,        0.00,  180),
    ("TAKEOFF",           5800, 1.00,     12.5,        0.05,  60),
    ("CLIMB",             5200, 0.85,     13.5,        0.55,  600),
    ("CRUISE_LOITER",     4200, 0.55,     15.0,        1.00,  3600),   # endurance stage
    ("DESCENT",           3000, 0.25,     14.7,        0.30,  480),
    ("LANDING",           2500, 0.20,     14.7,        0.05,  90),
    ("SHUTDOWN",          800,  0.00,     14.7,        0.00,  60),
]

STAGE_NAMES = [s[0] for s in STAGE_DEFINITIONS]


def normalize_dataset(payload: dict) -> dict:
    """Validate and normalize the editable JSON dataset contract."""
    if payload.get("schema_version") != 1:
        raise ValueError("dataset schema_version must be 1")
    stages = payload.get("stages")
    environments = payload.get("environments")
    fluctuation = payload.get("fluctuation")
    if not isinstance(stages, list) or not stages:
        raise ValueError("dataset stages must be a non-empty list")
    if not isinstance(environments, dict) or not environments:
        raise ValueError("dataset environments must be a non-empty object")
    if not isinstance(fluctuation, dict) or not fluctuation:
        raise ValueError("dataset fluctuation must be a non-empty object")

    normalized_stages = []
    for stage in stages:
        required = ("name", "rpm", "throttle", "afr", "altitude_frac", "default_duration_s")
        if any(key not in stage for key in required):
            raise ValueError(f"stage is missing one of: {', '.join(required)}")
        normalized_stages.append((
            str(stage["name"]), float(stage["rpm"]), float(stage["throttle"]),
            float(stage["afr"]), float(stage["altitude_frac"]), float(stage["default_duration_s"]),
        ))

    normalized_environments = {}
    for key, environment in environments.items():
        required = ("isa_dev_c", "cruise_altitude_m", "airfield_elevation_m", "label")
        if any(field not in environment for field in required):
            raise ValueError(f"environment '{key}' is missing one of: {', '.join(required)}")
        normalized_environments[str(key)] = (
            float(environment["isa_dev_c"]), float(environment["cruise_altitude_m"]),
            float(environment["airfield_elevation_m"]), str(environment["label"]),
        )

    normalized_fluctuation = {
        str(channel): (float(values[0]), float(values[1]))
        for channel, values in fluctuation.items()
        if isinstance(values, list) and len(values) == 2
    }
    if len(normalized_fluctuation) != len(fluctuation):
        raise ValueError("each fluctuation value must be [sigma_fraction, smoothing]")
    return {
        "schema_version": 1,
        "dataset_id": str(payload.get("dataset_id") or "custom_dataset"),
        "label": str(payload.get("label") or payload.get("dataset_id") or "Custom dataset"),
        "stages": normalized_stages,
        "environments": normalized_environments,
        "fluctuation": normalized_fluctuation,
    }


def load_dataset(path: str) -> dict:
    import json

    with open(path, encoding="utf-8") as dataset_file:
        return normalize_dataset(json.load(dataset_file))


# Environmental presets: (isa_dev_c, cruise_altitude_m, airfield_elevation_m, label)
ENVIRONMENT_PRESETS = {
    "standard_normal_altitude":  (0.0,  2500.0, 300.0, "Standard day, normal cruise altitude"),
    "hot_normal_altitude":       (30.0, 2500.0, 300.0, "Hot day (ISA+30), normal cruise altitude"),
    "cold_normal_altitude":      (-25.0, 2500.0, 300.0, "Cold day (ISA-25), normal cruise altitude"),
    "standard_high_altitude":    (0.0,  6000.0, 300.0, "Standard day, high-altitude cruise"),
    "hot_high_altitude":         (30.0, 6000.0, 300.0, "Hot day (ISA+30), high-altitude cruise"),
    "cold_high_altitude":        (-25.0, 6000.0, 300.0, "Cold day (ISA-25), high-altitude cruise"),
}


DEFAULT_DATASET = {
    "schema_version": 1,
    "dataset_id": "rotax914_baseline_dataset",
    "label": "Rotax 914 baseline dataset",
    "stages": STAGE_DEFINITIONS,
    "environments": ENVIRONMENT_PRESETS,
    "fluctuation": {
        "cht_c": (0.015, 0.90), "oil_temp_c": (0.012, 0.92),
        "oil_pressure_psi": (0.02, 0.85), "egt_c": (0.015, 0.88),
        "fuel_flow_lph": (0.03, 0.80), "vibration_g": (0.05, 0.70),
    },
}


def stage_altitude_m(altitude_frac: float, airfield_elevation_m: float, cruise_altitude_m: float) -> float:
    return airfield_elevation_m + altitude_frac * (cruise_altitude_m - airfield_elevation_m)


def build_reference_dataset():
    """One row per (environment preset x stage), steady-state expected values."""
    import physics_model as pm

    rows = []
    for env_key, (isa_dev_c, cruise_alt, airfield_elev, label) in ENVIRONMENT_PRESETS.items():
        for name, rpm, throttle, afr, alt_frac, _dur in STAGE_DEFINITIONS:
            altitude_m = stage_altitude_m(alt_frac, airfield_elev, cruise_alt)
            state = pm.expected_state(rpm, altitude_m, isa_dev_c, afr, throttle)
            row = {"environment": env_key, "environment_label": label, "stage": name}
            row.update(state)
            rows.append(row)
    return rows


if __name__ == "__main__":
    import csv

    rows = build_reference_dataset()
    out_path = "expected_values_reference.csv"
    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows ({len(ENVIRONMENT_PRESETS)} environments x {len(STAGE_DEFINITIONS)} stages) to {out_path}\n")
    for r in rows[:10]:
        print(r)
