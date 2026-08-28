# Backend Team Plan
**Role:** Managing data ingestion, API architecture, model inference integration, and database storage.

## Technology Stack
- **Language:** Python
- **Framework:** FastAPI (High-performance API layer)
- **Streaming:** MQTT (paho-mqtt) or WebSockets
- **Database:** SQLite (MVP) migrating to PostgreSQL (Final Production)
- **Version Control:** Git/GitHub setup & pipeline management

---

## Phase-Wise Build Plan

### **Phase 0: Foundation (Week 1)**
- **Task:** Set up the Git repository, shared folder structure, and Python virtual environments.
- **Task:** Define REST API and WebSocket contracts with the Frontend team.
- **Sync:** Review the JSON data schema provided by the ML team.

### **Phase 1: MVP - Ingestion & API (Weeks 2-3)**
- **Task:** Set up an MQTT broker or WebSocket listener to receive live telemetry from the ML team's synthetic generator.
- **Task:** Store all incoming time-series telemetry into an SQLite database (keyed by engine_id and timestamp).
- **Task:** Build basic FastAPI endpoints to serve the latest live sensor readings to the dashboard.
- **Sync:** Ensure Frontend can successfully read the raw data stream from the API.

### **Phase 2: Digital Twin Pipeline Integration (Weeks 4-5)**
- **Task:** Integrate the ML team's Physics-Informed models into the streaming pipeline.
- **Task:** As telemetry arrives, compute the real-time expected values and calculate deviations dynamically.
- **Task:** Serve the calculated "Health Indices" via the API.
- **Sync:** Verify Frontend receives both raw data and computed health scores simultaneously.

### **Phase 3: Fault Alerting System (Weeks 6-7)**
- **Task:** Embed the ML team's trained Isolation Forest model into the FastAPI inference pipeline.
- **Task:** Create logic to trigger and store fault alerts when anomaly scores cross the threshold.
- **Task:** Push categorized alerts to the Frontend instantly via WebSockets.
- **Sync:** Test the end-to-end alert latency from synthetic generation to UI display.

### **Phase 4: Predictive Endpoints (Weeks 8-9)**
- **Task:** Integrate the Remaining Useful Life (RUL) models into the backend.
- **Task:** Create endpoints that serve historical trend lines (e.g., last 2 hours of oil pressure) and RUL countdowns.
- **Task:** Serve maintenance recommendations based on RUL limits.
- **Sync:** Coordinate with Frontend on how trend data should be paginated or grouped.

### **Phase 5: Replay & Simulation API (Week 10)**
- **Task:** Implement historical data extraction API (querying past missions from SQLite/Postgres by date/mission ID).
- **Task:** Create controller endpoints to trigger specific "Mission Simulation Profiles" provided by the ML team.
- **Sync:** Provide the Frontend with API routes to act as a "Flight Recorder" scrubber.

### **Phase 6: Polish & Optimization (Weeks 11-12)**
- **Task:** Optimize database queries for faster historical replay.
- **Task:** Harden API endpoints (error handling, logging).
- **Task:** Finalize backend deployment scripts/Dockerfiles and architecture diagrams.
