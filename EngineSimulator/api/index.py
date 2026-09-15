import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
FRONTEND_APP = os.path.join(ROOT, "frontend", "app.py")

spec = importlib.util.spec_from_file_location("uav_frontend_app", FRONTEND_APP)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load frontend/app.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

app = module.app
