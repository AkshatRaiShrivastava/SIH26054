# Machine Learning & Data Team Plan
**Role:** Developing the synthetic data generator, physics-informed digital twin core, anomaly detection, and predictive RUL models.

## Technology Stack
- **Language:** Python
- **Data Handling:** Pandas, NumPy (for structuring, analyzing, and generating synthetic time-series data)
- **Anomaly Detection:** Scikit-learn (Isolation Forest / One-Class SVM)
- **RUL Prediction:** Scikit-learn (RandomForestRegressor, GradientBoosting) or optionally LSTM (TensorFlow/PyTorch)
- **Physics Layer:** Rule-based Python functions (Thermodynamic + Data-driven hybrid)

---

## Phase-Wise Build Plan

### **Phase 0: Foundation (Week 1)**
- **Task:** Define the exact sensor parameter schema (the 11 key parameters like RPM, CHT, EGT, Oil Pressure, etc.).
- **Task:** Research general-aviation reference ranges to establish realistic normal operating bounds and abnormal fault signatures.
- **Sync:** Hand off the JSON schema structure to the Backend and Frontend teams.

### **Phase 1: MVP - Synthetic Data Generation (Weeks 2-3)**
- **Task:** Build the synthetic sensor data generator.
- **Task:** Program a "healthy baseline" generator that scales parameters realistically against RPM.
- **Task:** Program "degradation injections" (e.g., slowly drifting oil pressure down by 0.5% per simulated hour to mimic a leak).
- **Sync:** Provide the synthetic data stream script to the Backend team so they can ingest it via MQTT/WebSockets.

### **Phase 2: Digital Twin Core & Health Index (Weeks 4-5)**
- **Task:** Develop the "Expected Behavior" physics models (e.g., calculating expected oil temp based on RPM and ambient temp).
- **Task:** Create the logic to compare expected vs. actual values to calculate a percentage-based deviation.
- **Task:** Formulate a weighted "Health Index" per subsystem (e.g., Lubrication Health = 90%).
- **Sync:** Hand off these Python functions to the Backend team to integrate into the live data pipeline.

### **Phase 3: Fault Detection (Weeks 6-7)**
- **Task:** Train the `IsolationForest` model on the synthetic healthy dataset.
- **Task:** Run injected-fault data through the model to validate anomaly detection and tune thresholds.
- **Task:** Map anomaly clusters to specific fault categories (e.g., "Combustion Instability", "Sensor Drift").
- **Sync:** Provide the trained model or scoring script to the Backend team to generate real-time alerts.

### **Phase 4: Predictive Analytics - RUL (Weeks 8-9)**
- **Task:** Extract trend features (e.g., rate of change of vibration over a 10-minute window).
- **Task:** Train a regression model (or LSTM) on degradation curves to estimate Remaining Useful Life (RUL) in flight hours.
- **Task:** Define rule-based maintenance recommendations tied to RUL thresholds.
- **Sync:** Hand off the RUL inference logic to the Backend.

### **Phase 5: Simulation Profiles (Week 10)**
- **Task:** Create specific mission-profile generation scripts (e.g., High-Altitude ISR, Hot-Weather Maritime Patrol) for the final demo.
- **Sync:** Ensure Backend can trigger these simulation profiles to feed live demo data to the Frontend.

### **Phase 6: Polish & Documentation (Weeks 11-12)**
- **Task:** Fine-tune model thresholds to reduce false positives.
- **Task:** Finalize ML documentation explaining the math behind the physics model and the ML architecture.
- **Task:** Rehearse the fault-injection demo script.
