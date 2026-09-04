# Project Structure Guide

## Digital Twin Pipeline - Organized Layout

```
SIH26054/
│
├── src/                          # 📦 Source Code (Core Application)
│   ├── core/                     # 🔧 Core Business Logic
│   │   ├── environmental_model.py       → Climate-zone dependent parameter generation
│   │   ├── environmental_physics.py     → Density altitude, icing risk, fault attribution
│   │   └── physics_layer.py             → Live physics evaluation & status updates
│   │
│   ├── database/                 # 🗄️  Database Layer
│   │   └── database.py                  → SQLite schema, connections, initialization
│   │
│   ├── app/                      # 🎯 Application Layer
│   │   └── dashboard.py                 → Streamlit interactive dashboard
│   │
│   └── utils/                    # 🛠️  Utilities & Helpers
│       ├── config.py                    → Centralized configuration & parameters
│       ├── utils.py                     → OU processes, seeding, debouncing, DA calc
│       ├── validate.py                  → Validation & data checks
│       └── generate_telemetry.py        → Flight telemetry generator
│
├── scripts/                      # 🚀 Executable Scripts
│   ├── quickstart.py                    → Quick start guide script
│   └── run_live_pipeline.py             → Live pipeline runner
│
├── tests/                        # ✅ Tests
│   └── test_setup.py                    → Setup & validation tests
│
├── data/                         # 💾 Data Files
│   ├── digital_twin.db                  → Main SQLite database (auto-generated)
│   └── debug_eval_state.db              → Debug evaluation state (auto-generated)
│
├── docs/                         # 📚 Documentation
│   ├── README.md                        → Main readme & quick start
│   ├── INDEX.md                         → File inventory & descriptions
│   ├── CONFIGURATION_GUIDE.md           → Configuration instructions
│   ├── IMPLEMENTATION_SUMMARY.md        → Implementation details
│   └── plan.md                          → Project plan
│
├── requirements.txt              # 📋 Python Dependencies
├── PROJECT_STRUCTURE.md          # 📖 This file
└── __pycache__/                  # (Auto-generated, can be ignored)
```

---

## 📁 Directory Breakdown

### `src/` - Source Code
The main application code organized by domain:
- **core/** - Business logic for physics, environmental modeling, and evaluations
- **database/** - Database layer (schema, connections)
- **app/** - User-facing applications (dashboard)
- **utils/** - Reusable utilities and configuration

### `scripts/` - Standalone Scripts
Executable scripts that can be run independently:
- Entry points for the application
- Testing and validation scripts

### `tests/` - Test Suite
All test files organized here.

### `data/` - Data Files
Generated database files and data artifacts:
- `.db` files are auto-generated (can be safely deleted and regenerated)

### `docs/` - Documentation
All markdown documentation for the project.

---

## 🔄 Next Steps

### 1. Move Core Files to `src/core/`
```powershell
Move-Item .\environmental_model.py .\src\core\
Move-Item .\environmental_physics.py .\src\core\
Move-Item .\physics_layer.py .\src\core\
```

### 2. Move Database Files to `src/database/`
```powershell
Move-Item .\database.py .\src\database\
```

### 3. Move App Files to `src/app/`
```powershell
Move-Item .\dashboard.py .\src\app\
```

### 4. Move Utility Files to `src/utils/`
```powershell
Move-Item .\config.py .\src\utils\
Move-Item .\utils.py .\src\utils\
Move-Item .\validate.py .\src\utils\
Move-Item .\generate_telemetry.py .\src\utils\
```

### 5. Move Scripts to `scripts/`
```powershell
Move-Item .\quickstart.py .\scripts\
Move-Item .\run_live_pipeline.py .\scripts\
```

### 6. Move Tests to `tests/`
```powershell
Move-Item .\test_setup.py .\tests\
```

### 7. Move Data Files to `data/`
```powershell
Move-Item .\digital_twin.db .\data\
Move-Item .\debug_eval_state.db .\data\
```

### 8. Move Documentation to `docs/`
```powershell
Move-Item .\README.md .\docs\
Move-Item .\INDEX.md .\docs\
Move-Item .\CONFIGURATION_GUIDE.md .\docs\
Move-Item .\IMPLEMENTATION_SUMMARY.md .\docs\
Move-Item .\plan.md .\docs\
```

### 9. Clean Up Root
Keep only:
- `requirements.txt`
- `PROJECT_STRUCTURE.md` (or move to docs/)
- New root level files if needed

---

## 🎯 Benefits of This Structure

✅ **Clear Separation of Concerns** - Core logic, utils, app, and data are isolated  
✅ **Easy to Navigate** - New developers can quickly find what they need  
✅ **Scalable** - Easy to add new modules (e.g., `src/services/`, `src/models/`)  
✅ **Professional** - Follows Python packaging best practices  
✅ **Modular** - Can easily convert to a proper Python package later  

---

## ⚙️ Import Updates Needed

Once files are moved, you'll need to update imports. For example:

**Before:**
```python
from config import ENGINE_PARAMS
from utils import seed_from_flight_id
from database import init_database
```

**After:**
```python
from src.utils.config import ENGINE_PARAMS
from src.utils.utils import seed_from_flight_id
from src.database.database import init_database
```

Alternatively, create `__init__.py` files for easier imports (discussed below).

---

## 🐍 Optional: Convert to Python Package

Create `__init__.py` files in each `src/` subdirectory:

```python
# src/__init__.py
from . import core, database, app, utils

# src/utils/__init__.py
from .config import *
from .utils import *
# etc.
```

This allows simpler imports:
```python
from src.utils import seed_from_flight_id
from src.core import environmental_physics
```

---

## 📝 Summary

**Current State:** All files in root directory (cluttered)  
**New State:** Organized into logical folders by functionality  
**Effort:** Move files using the commands above, update imports as needed  
**Benefit:** Professional, maintainable, scalable project structure
