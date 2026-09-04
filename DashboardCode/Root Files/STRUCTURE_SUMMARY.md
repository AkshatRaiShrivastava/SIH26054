# 📁 Project Structure - Complete Organization

## Visual Tree

```
SIH26054/
│
├── src/                          # 📦 Source Code (Core Application)
│   ├── __init__.py               # Package marker
│   │
│   ├── core/                     # 🔧 Core Business Logic (Physics & Environment)
│   │   ├── __init__.py
│   │   ├── environmental_model.py       (205 lines) Climate-zone dependent parameters
│   │   ├── environmental_physics.py     (277 lines) Density altitude, icing risk
│   │   └── physics_layer.py             (431 lines) Physics evaluation & debouncing
│   │
│   ├── database/                 # 🗄️ Database Layer
│   │   ├── __init__.py
│   │   └── database.py                  (178 lines) SQLite schema & connections
│   │
│   ├── app/                      # 🎯 Application Layer (UI)
│   │   ├── __init__.py
│   │   └── dashboard.py                 (550 lines) Streamlit dashboard
│   │
│   └── utils/                    # 🛠️ Utilities & Configuration
│       ├── __init__.py
│       ├── config.py                    (273 lines) Engine & environment parameters
│       ├── utils.py                     (359 lines) OU processes, math utilities
│       ├── validate.py                  (180 lines) Testing & validation
│       └── generate_telemetry.py        (286 lines) Flight telemetry generator
│
├── scripts/                      # 🚀 Executable Entry Points
│   ├── quickstart.py                    (140 lines) Quick start guide
│   └── run_live_pipeline.py             (120 lines) Live pipeline orchestrator
│
├── tests/                        # ✅ Test Suite
│   └── test_setup.py                    (100 lines) Setup & import verification
│
├── data/                         # 💾 Generated Data (Auto)
│   ├── digital_twin.db                  (Auto-generated)
│   └── debug_eval_state.db              (Auto-generated)
│
├── docs/                         # 📚 Documentation
│   ├── README.md                        Full documentation & quick start
│   ├── INDEX.md                         File inventory & descriptions
│   ├── CONFIGURATION_GUIDE.md           Configuration instructions
│   ├── IMPLEMENTATION_SUMMARY.md        Implementation details
│   └── plan.md                          Detailed project plan
│
├── requirements.txt              # 📋 Python Dependencies
├── PROJECT_STRUCTURE.md          # 📖 Structure guide document
└── STRUCTURE_SUMMARY.md          # 📄 This file
```

---

## 📋 Directory Reference

### `src/` - Main Application Source (5 subdirectories)

The heart of the application, organized by domain and responsibility:

#### `src/core/` - Physics & Environmental Logic
- **Purpose**: Core business logic for engine evaluation and environmental modeling
- **Files**:
  - `environmental_model.py` - Climate zone dependent parameters (humidity, altitude, precipitation)
  - `environmental_physics.py` - Physics corrections (density altitude, icing risk, fault attribution)
  - `physics_layer.py` - Main evaluation engine with debounced status tracking
- **When to modify**: When changing physics models or environmental effects

#### `src/database/` - Database Access Layer
- **Purpose**: SQLite schema, connection management, and initialization
- **Files**:
  - `database.py` - Database initialization, connection utilities
- **When to modify**: When changing schema or adding new tables

#### `src/app/` - Application Layer (UI)
- **Purpose**: User-facing applications and dashboards
- **Files**:
  - `dashboard.py` - Streamlit interactive dashboard with live and historical views
- **When to modify**: When adding new dashboard features or UI elements

#### `src/utils/` - Shared Utilities & Configuration
- **Purpose**: Reusable utilities, configuration, and helpers
- **Files**:
  - `config.py` - Centralized configuration (engine params, climate zones, fault profiles)
  - `utils.py` - Mathematical utilities (OU processes, seeding, debouncing, DA calculation)
  - `generate_telemetry.py` - Flight telemetry generation (uses config + utils)
  - `validate.py` - Testing and validation utilities
- **When to modify**: When adjusting parameters, adding new utilities, or changing business logic

### `scripts/` - Standalone Executable Scripts

Entry points and orchestration scripts:
- `quickstart.py` - Interactive quick-start guide (run from project root)
- `run_live_pipeline.py` - Launches all components for live monitoring (orchestrator)

**Usage**: Run from project root
```bash
python scripts/quickstart.py
python scripts/run_live_pipeline.py --flight-id FL-DEMO-001
```

### `tests/` - Test Suite

Quality assurance and validation:
- `test_setup.py` - Verifies imports, database initialization, and basic functionality

**Usage**: Run from project root
```bash
python -m tests.test_setup
```

### `data/` - Generated Data (Auto-created)

SQLite database files (auto-generated, safe to delete):
- `digital_twin.db` - Main application database
- `debug_eval_state.db` - Debug evaluation state

### `docs/` - Documentation

Markdown documentation files:
- `README.md` - Main documentation and quick start guide
- `INDEX.md` - File inventory with detailed descriptions
- `CONFIGURATION_GUIDE.md` - Configuration instructions
- `IMPLEMENTATION_SUMMARY.md` - Implementation details and rationale
- `plan.md` - Detailed project plan

---

## 🔄 Import Examples

### Inside `src/utils/generate_telemetry.py`
```python
from . import config                                      # from same package
from .utils import OUProcess, seed_from_flight_id        # from same package
from ..core.environmental_model import EnvironmentalModel # from sibling
from ..database.database import get_connection            # from database layer
```

### Inside `src/core/physics_layer.py`
```python
from ..utils import config                                # from utils
from ..database.database import get_connection            # from database
from .environmental_physics import EnvironmentalPhysics   # from same package
```

### From scripts (e.g., `scripts/quickstart.py`)
```python
sys.path.insert(0, PROJECT_ROOT)
from src.utils.config import DATABASE_PATH
from src.database.database import init_database
from src.utils.generate_telemetry import FlightGenerator
```

### From root (Python console or Jupyter)
```python
from src.utils import config
from src.core import PhysicsEvaluator
from src.database import get_connection
```

---

## 🎯 Using the New Structure

### Running from Project Root

**Generate telemetry:**
```bash
python -m src.utils.generate_telemetry --flight-id FL-001 --zone ior_maritime
```

**Evaluate physics:**
```bash
python -m src.core.physics_layer --flight-id FL-001 --replay
```

**Launch dashboard:**
```bash
streamlit run src/app/dashboard.py
```

**Run all together:**
```bash
python scripts/run_live_pipeline.py --flight-id FL-LIVE-001
```

**Quick start:**
```bash
python scripts/quickstart.py
```

### File Access

Database path is centralized in `src/utils/config.py`:
```python
DATABASE_PATH = os.path.join(BASE_DIR, "data", "digital_twin.db")
```

This means:
- Automatic creation of `data/` directory
- Consistent path used across all modules
- Easy to change in one place

---

## ✅ Benefits of This Structure

1. **Clear Separation of Concerns**
   - Core logic separate from app, utilities, and database
   - Easy to find code by functionality

2. **Professional Organization**
   - Follows Python packaging best practices
   - Scalable for future expansion

3. **Import Clarity**
   - Relative imports within `src/`
   - Absolute imports from scripts and tests
   - No circular dependencies

4. **Maintainability**
   - New developers can quickly understand layout
   - Each module has a single responsibility
   - Easy to add new modules without disruption

5. **Testability**
   - Proper package structure enables pytest discovery
   - Easy to mock and test components in isolation

6. **Extensibility**
   - Add new services: `src/services/`
   - Add new models: `src/models/`
   - Add API layer: `src/api/`

---

## 🔧 Configuration Management

The `src/utils/config.py` file is the single source of truth for:
- Engine parameters (Rotax 914 specifications)
- Expected sensor values and tolerances
- Noise models (OU process parameters)
- Climate zone definitions
- Fault profiles
- Debounce settings
- Database paths

**To adjust behavior**, modify `config.py` — no code changes needed elsewhere.

---

## 📊 Project Statistics

- **Total Files**: 34 (code + docs + config)
- **Python Modules**: 11
- **Lines of Code**: ~3,200
- **Documentation Files**: 6
- **Test Files**: 1

---

## 🚀 Next Steps

1. **Review imports** - Verify all files import correctly
2. **Run tests** - Use `python scripts/quickstart.py` to validate setup
3. **Generate data** - Run a sample flight to populate `data/digital_twin.db`
4. **Explore code** - Navigate by folder to understand each component
5. **Extend** - Add new features by creating new modules in appropriate `src/` subdirectories

---

## 📝 Notes

- The `__pycache__/` directory is auto-generated and can be safely ignored/deleted
- All database files are auto-generated and can be safely deleted (will be recreated)
- Configuration is centralized in one place for easy parameter adjustment
- All imports use relative paths within `src/` for maximum flexibility
