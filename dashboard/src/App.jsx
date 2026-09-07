import { useEffect, useMemo, useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

const phaseNames = { 0: 'POWER ON', 1: 'PREFLIGHT CHECK', 2: 'TAKEOFF', 3: 'CLIMB', 4: 'CRUISE / ISR', 5: 'DESCEND', 6: 'LAND' };
const defaultStageSeconds = { 0: 120, 1: 180, 2: 60, 3: 480, 4: 2400, 5: 300, 6: 60 };
const formatNumber = (value, digits = 1) => {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
};
const formatDate = (value) => value ? new Date(value).toLocaleString() : '—';
const formatTime = (seconds) => {
  const s = Math.max(0, Math.floor(Number(seconds) || 0));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
};

const metricCards = [
  { key: 'rpm', label: 'RPM (rev/min)' },
  { key: 'cht_c', label: 'CHT (°C)' },
  { key: 'egt_c', label: 'EGT (°C)' },
  { key: 'oil_pressure_kpa', label: 'Oil Pressure (kPa)' },
  { key: 'oil_temperature_c', label: 'Oil Temp (°C)' },
  { key: 'fuel_flow_lph', label: 'Fuel Flow (L/h)' },
  { key: 'vibration_mms', label: 'Vibration (mm/s)' },
  { key: 'afr', label: 'AFR (ratio)' },
  { key: 'battery_voltage', label: 'Battery (V)' },
  { key: 'altitude_m', label: 'Altitude (m)' },
  { key: 'ambient_temp_c', label: 'Ambient (°C)' },
];

const defaultPayload = {
  channel: 'live',
  mission_id: 'MISSION-0000',
  elapsed_s: 0,
  phase_id: 0,
  phase_name: 'POWER ON',
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
  const [missionDetails, setMissionDetails] = useState(null);
  const [stageSeconds, setStageSeconds] = useState(defaultStageSeconds);

  const refreshMissions = () => fetch(`${API_URL}/api/missions`).then((r) => r.json()).then(setMissions).catch(() => {});

  useEffect(() => {
    refreshMissions();
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
      body: JSON.stringify({
        scenario,
        speed_multiplier: Number(speedMultiplier),
        phase_durations_s: Object.fromEntries(Object.entries(stageSeconds).map(([stage, seconds]) => [stage, Math.max(1, Number(seconds))])),
      }),
    });
    const data = await response.json();
    setStatus((prev) => ({ ...prev, mission_id: data.mission_id, running: true, scenario }));
    refreshMissions();
  };

  useEffect(() => {
    if (!status.mission_id) return undefined;
    const timer = setInterval(async () => {
      const response = await fetch(`${API_URL}/api/simulation/status`);
      if (!response.ok) return;
      const current = await response.json();
      setStatus((previous) => ({ ...previous, running: current.running, status: current.status }));
      setPayload((previous) => ({
        ...previous,
        elapsed_s: current.elapsed_s ?? previous.elapsed_s,
        phase_id: current.phase_id ?? previous.phase_id,
        mission_total_s: current.mission_total_s ?? previous.mission_total_s,
        remaining_s: current.remaining_s ?? previous.remaining_s,
      }));
      if (!current.running) refreshMissions();
    }, 1000);
    return () => clearInterval(timer);
  }, [status.mission_id]);

  const stopSimulation = async () => {
    await fetch(`${API_URL}/api/simulation/stop`, { method: 'POST' });
    setStatus((prev) => ({ ...prev, running: false }));
  };

  const openMission = async (missionId) => {
    const response = await fetch(`${API_URL}/api/missions/${missionId}/details`);
    if (response.ok) setMissionDetails(await response.json());
  };

  const deleteMission = async (missionId) => {
    if (!window.confirm(`Delete ${missionId} and all of its telemetry?`)) return;
    await fetch(`${API_URL}/api/missions/${missionId}`, { method: 'DELETE' });
    setMissionDetails(null);
    refreshMissions();
  };

  const clearHistory = async () => {
    if (!window.confirm('Clear all flight history and telemetry?')) return;
    await fetch(`${API_URL}/api/missions`, { method: 'DELETE' });
    setMissionDetails(null);
    refreshMissions();
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
          <label>Simulation Status <strong>{status.running ? 'RUNNING' : (status.status === 'completed' ? 'COMPLETED' : 'READY')}</strong></label>
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
        <div className="stage-duration-panel">
          <div className="stage-duration-title">STAGE DURATION (SECONDS)</div>
          <div className="stage-duration-grid">
            {Object.entries(phaseNames).map(([stage, name]) => (
              <label key={stage}>{name}
                <input type="number" min="1" step="1" value={stageSeconds[stage]} onChange={(event) => setStageSeconds((current) => ({ ...current, [stage]: event.target.value }))} />
              </label>
            ))}
          </div>
        </div>
        {status.mission_id && payload.mission_total_s > 0 && (
          <div className="mission-timer-panel">
            <div className="timer-row">
              <span className="timer-label">ELAPSED</span>
              <span className="timer-value">{formatTime(payload.elapsed_s)}</span>
            </div>
            <div className="timer-row">
              <span className="timer-label">TOTAL</span>
              <span className="timer-value">{formatTime(payload.mission_total_s)}</span>
            </div>
            <div className="timer-row remaining">
              <span className="timer-label">REMAINING</span>
              <span className="timer-value">{formatTime(payload.remaining_s)}</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${Math.min(100, Math.max(0, (payload.elapsed_s / payload.mission_total_s) * 100))}%` }} />
            </div>
          </div>
        )}
      </section>

      <section className="summary-grid">
        <div className="info-card">
          <div className="label">MISSION</div>
          <div className="value">{status.mission_id || 'MISSION-0000'}</div>
        </div>
        <div className="info-card">
          <div className="label">PHASE</div>
          <div className="value phase-value"><span>{payload.phase_name || phaseNames[payload.phase_id] || 'UNKNOWN'}</span><small>Stage {payload.phase_id}</small></div>
        </div>
        <div className="info-card">
          <div className="label">ENGINE HEALTH</div>
          <div className={`value ${healthTone}`}>{Math.round(payload.computed.health_index || 100)} / 100</div>
        </div>
        <div className="info-card">
          <div className="label">RUL</div>
          <div className="value">{payload.rul.predicted_rul_minutes != null ? `${formatNumber(payload.rul.predicted_rul_minutes, 1)} min` : 'ESTIMATING...'}</div>
        </div>
      </section>

      <section className="panel-grid">
        <div className="card wide">
          <div className="panel-header">LIVE FLIGHT DATA</div>
          <div className="telemetry-grid">
            {metricCards.map((item) => (
              <div className="telemetry-card" key={item.key}>
                <div className="label">{item.label}</div>
                <div className="value">{formatNumber(payload.raw[item.key], item.key === 'afr' || item.key === 'vibration_mms' ? 2 : 0)}</div>
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
                <td>CHT (°C)</td>
                <td>{formatNumber(payload.physics.cht.actual)}</td>
                <td>{formatNumber(payload.physics.cht.expected)}</td>
                <td>{formatNumber(payload.physics.cht.residual, 2)}</td>
                <td>{formatNumber(payload.physics.cht.deviation_pct, 2)}%</td>
              </tr>
              <tr>
                <td>EGT (°C)</td>
                <td>{formatNumber(payload.physics.egt.actual)}</td>
                <td>{formatNumber(payload.physics.egt.expected)}</td>
                <td>{formatNumber(payload.physics.egt.residual, 2)}</td>
                <td>{formatNumber(payload.physics.egt.deviation_pct, 2)}%</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="panel-header">AI / ML ANOMALY DETECTION</div>
          <div className="metric-stack">
            <div>Anomaly Score: {formatNumber(payload.computed.anomaly_score, 3)}</div>
            <div>Status: {payload.computed.is_anomaly ? '⚠ ANOMALY DETECTED' : '✓ NO ANOMALY DETECTED'}</div>
            <div>Health Index: {formatNumber(payload.computed.health_index, 1)} / 100</div>
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
            <div>{payload.rul.predicted_rul_minutes != null ? `${formatNumber(payload.rul.predicted_rul_minutes, 1)} min` : 'ESTIMATING...'}</div>
            <small>± {payload.rul.confidence_band_minutes != null ? `${formatNumber(payload.rul.confidence_band_minutes, 1)} min` : 'n/a'}</small>
            <div>Driving factor: {payload.rul.driving_channel || 'n/a'}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="history-header"><div className="panel-header">FLIGHT HISTORY</div><button className="danger-button" onClick={clearHistory} disabled={!missions.length}>CLEAR ALL</button></div>
        <table>
          <thead>
            <tr><th>Mission ID</th><th>Scenario</th><th>Status</th><th>Started</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {missions.map((m) => (
              <tr key={m.mission_id}>
                <td><button className="link-button" onClick={() => openMission(m.mission_id)}>{m.mission_id}</button></td>
                <td>{m.scenario}</td>
                <td>{m.status}</td>
                <td>{formatDate(m.started_at)}</td>
                <td><button className="small-button" onClick={() => openMission(m.mission_id)}>DETAILS</button><button className="small-button danger-button" onClick={() => deleteMission(m.mission_id)}>DELETE</button></td>
              </tr>
            ))}
            {!missions.length && <tr><td colSpan="5" className="empty-state">No flight history</td></tr>}
          </tbody>
        </table>
      </section>

      {missionDetails && <div className="modal-backdrop" onClick={() => setMissionDetails(null)}><section className="details-modal" onClick={(event) => event.stopPropagation()}>
        <div className="history-header"><div><div className="panel-header">FLIGHT DETAILS</div><h2>{missionDetails.mission_id}</h2></div><button className="secondary" onClick={() => setMissionDetails(null)}>CLOSE</button></div>
        <div className="detail-grid"><div><span>Scenario</span><strong>{missionDetails.scenario}</strong></div><div><span>Status</span><strong>{missionDetails.status}</strong></div><div><span>Started</span><strong>{formatDate(missionDetails.started_at)}</strong></div><div><span>Samples</span><strong>{missionDetails.summary.samples}</strong></div><div><span>Average health</span><strong>{formatNumber(missionDetails.summary.average_health, 1)} / 100</strong></div><div><span>Peak anomaly</span><strong>{formatNumber(missionDetails.summary.peak_anomaly, 3)}</strong></div></div>
        <h3>Latest telemetry</h3>{missionDetails.latest ? <div className="detail-telemetry">{metricCards.map((item) => <div key={item.key}><span>{item.label}</span><strong>{formatNumber(missionDetails.latest[item.key], item.key === 'afr' || item.key === 'vibration_mms' ? 2 : 0)}</strong></div>)}</div> : <p>No telemetry recorded.</p>}
        <h3>Fault events</h3>{missionDetails.faults.length ? missionDetails.faults.map((fault, index) => <div className="fault-row" key={`${fault.category}-${index}`}><strong>{fault.category}</strong><span>{fault.confidence} · {fault.features.join(', ')}</span></div>) : <p>No fault events recorded.</p>}
      </section></div>}
    </div>
  );
}

export default App;
