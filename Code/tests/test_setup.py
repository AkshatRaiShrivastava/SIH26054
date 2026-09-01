#!/usr/bin/env python
"""Quick test to verify database and imports work."""

import os
import sys

# Test imports
print("Testing imports...")
try:
    from src.database.database import init_database, get_connection, close_connection
    print("  ✓ database module loaded")
    
    from src.utils.config import ENGINE_CONFIG, MISSION_PHASES, EXPECTED_VALUES_NOMINAL
    print("  ✓ config module loaded")
    
    from src.utils.utils import OUProcess, seed_from_flight_id, get_phase_at_time
    print("  ✓ utils module loaded")
    
    from src.core.environmental_model import EnvironmentalModel
    print("  ✓ environmental_model module loaded")
    
    from src.core.environmental_physics import EnvironmentalPhysics
    print("  ✓ environmental_physics module loaded")
    
    from src.utils.generate_telemetry import FlightGenerator
    print("  ✓ generate_telemetry module loaded")
    
    from src.core.physics_layer import PhysicsEvaluator
    print("  ✓ physics_layer module loaded")
    
    print("\n✓ All imports successful!\n")
except Exception as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)

# Test database
print("Testing database...")
try:
    from src.utils import config
    if os.path.exists(config.DATABASE_PATH):
        os.remove(config.DATABASE_PATH)
    
    init_database()
    print("  ✓ Database initialized")
    
    import sqlite3
    conn = sqlite3.connect(config.DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    print(f"  ✓ Tables created: {tables}")
    
    expected_tables = {"flights", "telemetry", "evaluations", "flight_condition", "corrosion_tracking"}
    if expected_tables == set(tables):
        print("  ✓ All required tables present")
    else:
        missing = expected_tables - set(tables)
        print(f"  ✗ Missing tables: {missing}")
        sys.exit(1)
    
    conn.close()
    print("\n✓ Database test passed!\n")
except Exception as e:
    print(f"✗ Database test failed: {e}")
    sys.exit(1)

# Test utility functions
print("Testing utility functions...")
try:
    from utils import seed_from_flight_id, OUProcess, classify_icing_risk
    
    # Test reproducible seeding
    seed1 = seed_from_flight_id("FL-TEST-001")
    seed2 = seed_from_flight_id("FL-TEST-001")
    assert seed1 == seed2, "Seeds should be identical"
    print(f"  ✓ Reproducible seeding: seed={seed1}")
    
    # Test OU process
    rng = __import__("random").Random(seed1)
    ou = OUProcess(mean=100, theta=0.1, sigma=5)
    value = ou.step(rng=rng)
    print(f"  ✓ OU process step: {value:.2f}")
    
    # Test icing risk
    risk = classify_icing_risk(5, 60)  # 5°C, 60% RH
    assert risk == "HIGH", f"Expected HIGH, got {risk}"
    print(f"  ✓ Icing risk classification: {risk}")
    
    print("\n✓ Utility functions test passed!\n")
except Exception as e:
    print(f"✗ Utility functions test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test environmental models
print("Testing environmental models...")
try:
    from environmental_model import EnvironmentalModel
    from environmental_physics import EnvironmentalPhysics
    
    rng = __import__("random").Random(42)
    env_model = EnvironmentalModel("ior_maritime", "AIRFRAME-TEST", rng)
    
    climate_zone_def = config.CLIMATE_ZONES["ior_maritime"]
    env_packet = env_model.get_environmental_packet(3000, climate_zone_def, "cruise", 2.5)
    print(f"  ✓ Environmental model: humidity={env_packet['humidity_pct']:.1f}%")
    
    env_phys = EnvironmentalPhysics()
    da, pwr = env_phys.compute_density_altitude_correction(3000, 5, 2900)
    print(f"  ✓ Density altitude: {da:.0f}m, power factor: {pwr:.2f}")
    
    print("\n✓ Environmental models test passed!\n")
except Exception as e:
    print(f"✗ Environmental models test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 70)
print("✓ ALL TESTS PASSED!")
print("=" * 70)
print("\nYour Digital Twin Pipeline is ready. Next steps:\n")
print("1. Run: python generate_telemetry.py --flight-id FL-DEMO-001 --zone ior_maritime --fault-chance 0.3")
print("2. Then: python physics_layer.py --flight-id FL-DEMO-001 --replay")
print("3. Finally: streamlit run dashboard.py")
print("\nFor detailed instructions, see README.md")
