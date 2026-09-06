"""
API client service for Streamlit Admin Console to interact with FastAPI Backend.
"""

import requests
from typing import Dict, Any, List, Optional

BACKEND_URL = "http://localhost:8000"


class APIClient:
    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = base_url

    def get_status(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/live/status", timeout=2.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {
            "can": "DISCONNECTED",
            "backend": "OFFLINE",
            "postgresql": "DISCONNECTED",
            "physics_engine": "UNAVAILABLE",
            "ai_engine": "MODEL NOT ACTIVE",
            "active_flight": "NONE",
            "flight_status": "IDLE",
        }

    def create_flight(self, label: str = "flight", mission_type: str = "surveillance", notes: str = "") -> Dict[str, Any]:
        try:
            r = requests.post(
                f"{self.base_url}/api/flights",
                params={"label": label, "mission_type": mission_type, "notes": notes},
                timeout=3.0,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Failed to create flight"}

    def start_flight(self, flight_id: str) -> Dict[str, Any]:
        try:
            r = requests.post(f"{self.base_url}/api/flights/{flight_id}/start", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Failed to start flight"}

    def stop_flight(self, flight_id: str) -> Dict[str, Any]:
        try:
            r = requests.post(f"{self.base_url}/api/flights/{flight_id}/stop", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Failed to stop flight"}

    def get_flights(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/flights", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def get_flight_detail(self, flight_id: str) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/flights/{flight_id}", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def get_flight_telemetry(self, flight_id: str) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/flights/{flight_id}/telemetry", timeout=5.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def get_flight_physics(self, flight_id: str) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/flights/{flight_id}/physics", timeout=5.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def get_flight_maintenance(self, flight_id: str) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/flights/{flight_id}/maintenance", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def get_live_telemetry(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/live/telemetry", timeout=1.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def get_live_physics(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/live/physics", timeout=1.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def get_live_health(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/live/health", timeout=1.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {"engine_health": 100.0, "anomaly_score": 0.0, "current_fault": "NONE", "rul": "Model not active"}

    def get_live_maintenance(self) -> List[Dict[str, Any]]:
        try:
            r = requests.get(f"{self.base_url}/api/live/maintenance", timeout=1.5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def start_simulator(self, mission: str = "surveillance", speed: float = 1.0, fault: str = "") -> Dict[str, Any]:
        try:
            r = requests.post(
                f"{self.base_url}/api/simulator/start",
                params={"mission": mission, "speed": speed, "fault": fault},
                timeout=5.0,
            )
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Failed to start simulator"}

    def stop_simulator(self) -> Dict[str, Any]:
        try:
            r = requests.post(f"{self.base_url}/api/simulator/stop", timeout=3.0)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            return {"error": str(e)}
        return {"error": "Failed to stop simulator"}

    def get_simulator_status(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/simulator/status", timeout=2.0)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {"running": False}


api_client = APIClient()
