# Frontend & UI Team Plan
**Role:** Building the real-time visualization dashboard, user experience, and interactive mission replay controls.

## Technology Stack
- **MVP / Prototyping:** Streamlit (Python-only, fast to build)
- **Final Product (Optional but Recommended):** React.js + Tailwind CSS (or standard CSS) + Chart.js / Recharts
- **Communication:** Axios/Fetch for REST, native WebSocket APIs for live data

---

## Phase-Wise Build Plan

### **Phase 0: Foundation (Week 1)**
- **Task:** Design the dashboard layout and wireframes. Prioritize legibility: raw parameters, health gauges, active alerts, and trend charts.
- **Task:** Decide whether to stick with Streamlit entirely or transition to React for Phase 6.
- **Sync:** Agree on REST API and WebSocket JSON payload structures with the Backend team.

### **Phase 1: MVP - Raw Telemetry Dashboard (Weeks 2-3)**
- **Task:** Build a barebones Streamlit (or basic React) dashboard.
- **Task:** Connect to Backend FastAPI endpoints to display live, raw parameter values in real-time.
- **Task:** Implement a basic multi-line chart for key parameters (e.g., CHT, RPM).
- **Sync:** Validate that the dashboard updates smoothly as the ML generator pumps data through the backend.

### **Phase 2: Health Monitoring UI (Weeks 4-5)**
- **Task:** Update the dashboard to visualize "Subsystem Health Status".
- **Task:** Implement color-coded gauges or progress bars (e.g., Green = Nominal, Amber = Warning, Red = Critical) based on health indices.
- **Sync:** Ensure Backend health index APIs map correctly to UI components.

### **Phase 3: Fault Alerts & Notifications (Weeks 6-7)**
- **Task:** Add a prominent "Active Alerts" panel.
- **Task:** Handle incoming WebSocket anomaly alerts and display them with fault category, timestamp, and confidence level.
- **Task:** Implement visual indicators (e.g., flashing red borders) when a critical fault is detected.
- **Sync:** Conduct an end-to-end test where ML injects a fault, and the UI reacts immediately.

### **Phase 4: Predictive Analytics Dashboards (Weeks 8-9)**
- **Task:** Build trend analysis visualizations to show degradation curves over time (e.g., slowly decaying oil pressure chart).
- **Task:** Display the Remaining Useful Life (RUL) prominently (e.g., "Estimated 14.5 flight hours to threshold").
- **Task:** Display actionable maintenance recommendations.
- **Sync:** Consume the RUL and historical trend APIs from the Backend.

### **Phase 5: Mission Replay & Simulator Controls (Week 10)**
- **Task:** Build a "Mission Selector" interface to trigger specific high-altitude or hot-weather simulations.
- **Task:** Build a "Historical Replay" control (like a flight-data recorder with play/pause/scrub timeline).
- **Sync:** Connect UI controls to Backend Simulation and Replay controller endpoints.

### **Phase 6: Visual Polish & Demo Prep (Weeks 11-12)**
- **Task:** Apply premium UI/UX aesthetics. Use modern typography, dark-mode themes (standard for aviation/defense software), and micro-animations for real-time data changes.
- **Task:** Ensure responsiveness and robust error handling if the data stream drops.
- **Task:** Rehearse the live demo scenario, ensuring the UI clearly communicates the value of predicting a fault before it causes a failure.
