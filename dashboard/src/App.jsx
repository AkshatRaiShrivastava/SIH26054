import { useEffect, useMemo, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

const metricCards = [
  { key: 'rpm', label: 'RPM' },
  { key: 'cht_c', label: 'CHT' },
  { key: 'egt_c', label: 'EGT' },
  { key: 'oil_pressure_kpa', label: 'Oil Pressure' },
  { key: 'oil_temperature_c', label: 'Oil Temp' },
  { key: 'fuel_flow_lph', label: 'Fuel Flow' },
  { key: 'vibration_mms', label: 'Vibration' },
  { key: 'afr', label: 'AFR' },
  { key: 'battery_voltage', label: 'Battery' },
  { key: 'altitude_m', label: 'Altitude' },
  { key: 'ambient_temp_c', label: 'Ambient' },
];

const defaultPayload = {
  channel: 'live',
  mission_id: 'MISSION-0000',
  elapsed_s: 0,
  phase_id: 0,
  raw: {
    rpm: 0,
    cht_c: 0,
    egt_c: 0,
    oil_pressure_kpa: 0,
    oil_temperature_c: 0,
    fuel_flow_lph: 0,
    vibration_mms: 0,
    afr: 14.7,
    battery_voltage: 0,
    altitude_m: 0,
    ambient_temp_c: 15,
  },
  computed: {
    health_index: 100,
    anomaly_score: 0,
    is_anomaly: false,
    deviations_pct: {
      cht: 0,
      egt: 0,
      oil_pressure: 0,
      oil_temp: 0,
      fuel_flow: 0,
      vibration: 0,
    },
  },
  physics: {
    cht: { actual: 0, expected: 0, residual: 0, deviation_pct: 0 },
    egt: { actual: 0, expected: 0, residual: 0, deviation_pct: 0 },
  },
  fault_alert: null,
  rul: { predicted_rul_minutes: null, confidence_band_minutes: null, driving_channel: null },
};

function App() {
  const [status, setStatus] = useState({ running: false, mission_id: null, scenario: 'normal' });
  const [payload, setPayload] = useState(defaultPayload);
  const [scenario, setScenario] = useState('normal');
  const [speedMultiplier, setSpeedMultiplier] = useState(1);
  const [connected, setConnected] = useState(false);
  const [missions, setMissions] = useState([]);

  useEffect(() => {
    fetch(`${API_URL}/api/missions`).then((r) => r.json()).then(setMissions).catch(() => setMissions([]));
  }, []);

  useEffect(() => {
    const socket = new WebSocket(`${WS_URL}/ws/live/${status.mission_id || 'demo'}`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPayload(data);
    };
    return () => socket.close();
  }, [status.mission_id]);

  const startSimulation = async () => {
    const response = await fetch(`${API_URL}/api/simulation/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, speed_multiplier: Number(speedMultiplier) }),
    });
    const data = await response.json();
    setStatus((prev) => ({ ...prev, mission_id: data.mission_id, running: true, scenario }));
    fetch(`${API_URL}/api/missions`).then((r) => r.json()).then(setMissions).catch(() => {});
  };

  const stopSimulation = async () => {
    await fetch(`${API_URL}/api/simulation/stop`, { method: 'POST' });
    setStatus((prev) => ({ ...prev, running: false }));
  };

  const healthTone = useMemo(() => {
    const value = Number(payload.computed.health_index ?? 100);
    if (value >= 80) return 'good';
    if (value >= 50) return 'warn';
    return 'danger';
  }, [payload.computed.health_index]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="eyebrow">SIH 2026 • DRDO</div>
          <h1>UAV ENGINE DIGITAL TWIN</h1>
        </div>
        <div className="header-status">
          <span className={`status-dot ${connected ? 'online' : 'offline'}`} />
          {connected ? 'CONNECTED' : 'DISCONNECTED'}
        </div>
      </header>

      <section className="sim-panel">
        <div className="panel-header">SIMULATION</div>
        <div className="sim-grid">
          <label>Mission ID <strong>{status.mission_id || 'PENDING'}</strong></label>
          <label>Simulation Status <strong>{status.running ? 'RUNNING' : 'READY'}</strong></label>
          <label>Scenario
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              <option value="normal">Normal</option>
              <option value="injector-degradation">Injector Degradation</option>
              <option value="lubrication-degradation">Lubrication Degradation</option>
              <option value="vibration-degradation">Vibration Degradation</option>
              <option value="overheating">Overheating</option>
              <option value="misfire">Misfire</option>
              <option value="electrical-issue">Electrical Issue</option>
              <option value="sensor-drift">Sensor Drift</option>
              <option value="degradation-demo">Degradation Demo</option>
            </select>
          </label>
          <label>Speed Multiplier
            <input type="number" min="1" max="20" step="1" value={speedMultiplier} onChange={(e) => setSpeedMultiplier(e.target.value)} />
          </label>
          <button onClick={startSimulation}>START SIMULATION</button>
          <button className="secondary" onClick={stopSimulation}>STOP SIMULATION</button>
        </div>
      </section>

      <section className="summary-grid">
        <div className="info-card">
          <div className="label">MISSION</div>
          <div className="value">{status.mission_id || 'MISSION-0000'}</div>
        </div>
        <div className="info-card">
          <div className="label">PHASE</div>
          <div className="value">{payload.phase_id}</div>
        </div>
        <div className="info-card">
          <div className="label">ENGINE HEALTH</div>
          <div className={`value ${healthTone}`}>{Math.round(payload.computed.health_index || 100)} / 100</div>
        </div>
        <div className="info-card">
          <div className="label">RUL</div>
          <div className="value">{payload.rul.predicted_rul_minutes ?? 'ESTIMATING...'}</div>
        </div>
      </section>

      <section className="panel-grid">
        <div className="card wide">
          <div className="panel-header">LIVE FLIGHT DATA</div>
          <div className="telemetry-grid">
            {metricCards.map((item) => (
              <div className="telemetry-card" key={item.key}>
                <div className="label">{item.label}</div>
                <div className="value">{payload.raw[item.key] ?? 0}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="panel-header">PHYSICS DIGITAL TWIN</div>
          <table>
            <thead>
              <tr><th>Parameter</th><th>Actual</th><th>Expected</th><th>Residual</th><th>Deviation</th></tr>
            </thead>
            <tbody>
              <tr>
                <td>CHT</td>
                <td>{payload.physics.cht.actual}</td>
                <td>{payload.physics.cht.expected}</td>
                <td>{payload.physics.cht.residual}</td>
                <td>{payload.physics.cht.deviation_pct}%</td>
              </tr>
              <tr>
                <td>EGT</td>
                <td>{payload.physics.egt.actual}</td>
                <td>{payload.physics.egt.expected}</td>
                <td>{payload.physics.egt.residual}</td>
                <td>{payload.physics.egt.deviation_pct}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="panel-header">AI / ML ANOMALY DETECTION</div>
          <div className="metric-stack">
            <div>Anomaly Score: {payload.computed.anomaly_score}</div>
            <div>Status: {payload.computed.is_anomaly ? '⚠ ANOMALY DETECTED' : '✓ NO ANOMALY DETECTED'}</div>
            <div>Health Index: {payload.computed.health_index}</div>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">RULE-BASED FAULT ANALYSIS</div>
          <div className="metric-stack">
            {payload.fault_alert ? (
              <>
                <div>Possible Fault: {payload.fault_alert.fault_category.toUpperCase()}</div>
                <div>Confidence: {payload.fault_alert.confidence.toUpperCase()}</div>
                <div>Driving Parameters: {payload.fault_alert.driving_features.join(', ')}</div>
              </>
            ) : (
              <div>No active fault</div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="panel-header">ENGINE HEALTH INDEX</div>
          <div className={`gauge ${healthTone}`}>
            <div className="gauge-inner">{Math.round(payload.computed.health_index || 100)}</div>
          </div>
        </div>

        <div className="card">
          <div className="panel-header">REMAINING USEFUL LIFE</div>
          <div className="rul-box">
            <div>{payload.rul.predicted_rul_minutes ?? 'ESTIMATING...'}</div>
            <small>± {payload.rul.confidence_band_minutes ?? 'n/a'} min</small>
            <div>Driving factor: {payload.rul.driving_channel || 'n/a'}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="panel-header">FLIGHT HISTORY</div>
        <table>
          <thead>
            <tr><th>Mission ID</th><th>Scenario</th><th>Status</th><th>Started</th></tr>
          </thead>
          <tbody>
            {missions.map((m) => (
              <tr key={m.mission_id}>
                <td>{m.mission_id}</td>
                <td>{m.scenario}</td>
                <td>{m.status}</td>
                <td>{m.started_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

export default App;
