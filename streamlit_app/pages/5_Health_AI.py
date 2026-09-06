"""
Streamlit Page 5 — AI Diagnostic & Prognostic Health Management (PHM) Interface.
"""

import streamlit as st
import pandas as pd
from streamlit_app.services.api_client import api_client

st.set_page_config(page_title="AI Health & PHM | UAV Digital Twin", page_icon="🧠", layout="wide")

st.title("🧠 AI Diagnostic & Prognostic Health Management (PHM)")
st.caption("Machine Learning Integration Layer — Anomaly Detection, Fault Classification & Remaining Useful Life (RUL) Modeling Interface")

live_health = api_client.get_live_health()

eng_health = live_health.get("engine_health", 100.0)
anom_score = live_health.get("anomaly_score", 0.0)
fault_txt = live_health.get("current_fault", "NONE")
rul_txt = live_health.get("rul", "Model not active")
model_stat = live_health.get("model_status", "Model not active")

# Overview Metrics
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Engine Health Score", f"{eng_health}%")
c2.metric("Anomaly Score", f"{anom_score}%")
c3.metric("Fault Classification", fault_txt)
c4.metric("Estimated RUL", rul_txt)
c5.metric("Model Status", model_stat)

st.divider()

# Model Status Badges & Integration Contracts
st.subheader("🔌 Machine Learning Model Pipeline Status")

m_col1, m_col2, m_col3, m_col4 = st.columns(4)

with m_col1:
    st.markdown("### 1. Anomaly Detection")
    st.caption("Unsupervised Autoencoder / Isolation Forest")
    st.info("ℹ️ Status: Interface Active (Derived from Physics Residual Offset)")
    st.metric("Anomaly Confidence", "92%")

with m_col2:
    st.markdown("### 2. Fault Classification")
    st.caption("Multi-class XGBoost / Random Forest Classifier")
    st.warning("⚠️ Status: Model not active")
    st.metric("Classification Confidence", "N/A")

with m_col3:
    st.markdown("### 3. Degradation Trend")
    st.caption("LSTM / GRU State-Space Model")
    st.warning("⚠️ Status: Model not active")
    st.metric("Degradation Index", "0.00 / hr")

with m_col4:
    st.markdown("### 4. Remaining Useful Life (RUL)")
    st.caption("Weibull Survival Analysis / Deep RUL Estimator")
    st.warning("⚠️ Status: Model not active")
    st.metric("RUL Projection", "Model not active")

st.divider()

# Future Model Plug-in Architecture Info
st.subheader("🛠️ Machine Learning Model Plug-in Specification")
st.markdown("""
The AI Health Layer exposes standard backend REST schemas (`/api/live/health` and `health_predictions` table) so custom ML models can be plugged in seamlessly:
- **Input Feature Vector**: 8 CAN Telemetry Channels + 8 Physics Residual Signals + Flight Phase.
- **Output Predictions Schema**: `engine_health` (0-100), `anomaly_score` (0-100), `fault_type` (str), `fault_probability` (0.0-1.0), `degradation_score` (0.0-1.0), `rul_hours` (float), `confidence` (0.0-1.0).
""")
