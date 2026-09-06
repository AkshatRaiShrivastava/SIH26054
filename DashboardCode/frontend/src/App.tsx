import { useMemo, useState, useEffect } from 'react';
import { ConnectionStatus } from './components/ConnectionStatus';
import { DataHealthPanel } from './components/DataHealth';
import { EngineStatus } from './components/EngineStatus';
import { TelemetryCard } from './components/TelemetryCard';
import { TelemetryChart } from './components/TelemetryChart';
import { MissionTimeline } from './components/MissionTimeline';
import { useTelemetry } from './hooks/useTelemetry';
import { useFlights, Flight } from './hooks/useFlights';
import type { DataHealth, EngineTelemetry } from './types/telemetry';

const signalKeys: Array<keyof EngineTelemetry> = [
  'rpm',
  'cht',
  'egt',
  'oil_pressure',
  'oil_temperature',
  'fuel_flow',
  'vibration',
  'battery_voltage',
  'mission_stage',
  'altitude',
  'throttle',
  'load',
];

function getSignalFreshness(dataHealth: DataHealth | null, key: keyof EngineTelemetry) {
  return dataHealth?.signal_freshness?.[String(key)]?.fresh ?? false;
}

function getTrend(history: EngineTelemetry[], key: keyof EngineTelemetry) {
  if (history.length < 2) return null;
  const previous = history[history.length - 2][key] as number;
  const current = history[history.length - 1][key] as number;
  if (current > previous) return 'up' as const;
  if (current < previous) return 'down' as const;
  return 'flat' as const;
}

export default function App() {
  const { telemetry, history, dataHealth, backendHealth, connectionState, lastUpdate, stale } = useTelemetry();
  const { flights, loading: flightsLoading, fetchFlights, createFlight, startFlight, stopFlight } = useFlights();

  const [activeFlightId, setActiveFlightId] = useState<string | null>(null);
  const [simStatus, setSimStatus] = useState<'IDLE' | 'RUNNING' | 'ERROR'>('IDLE');

  useEffect(() => {
    fetchFlights();
    async function initStatus() {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL}/api/live/status`);
        const data = await res.json();
        if (data.active_flight && data.active_flight !== 'NONE') {
          setActiveFlightId(data.active_flight);
        }
        if (data.flight_status === 'RUNNING') {
          setSimStatus('RUNNING');
        }
      } catch (e) {
        console.error('Failed to fetch initial status:', e);
      }
    }
    initStatus();
  }, [fetchFlights]);

  const cards = useMemo(
    () => [
      { label: 'RPM', key: 'rpm' as const, value: telemetry?.rpm ?? null, unit: 'rpm' },
      { label: 'CHT', key: 'cht' as const, value: telemetry?.cht ?? null, unit: '°C' },
      { label: 'EGT', key: 'egt' as const, value: telemetry?.egt ?? null, unit: '°C' },
      { label: 'Oil Pressure', key: 'oil_pressure' as const, value: telemetry?.oil_pressure ?? null, unit: 'kPa' },
      { label: 'Oil Temperature', key: 'oil_temperature' as const, value: telemetry?.oil_temperature ?? null, unit: '°C' },
      { label: 'Fuel Flow', key: 'fuel_flow' as const, value: telemetry?.fuel_flow ?? null, unit: 'L/h' },
      { label: 'Vibration', key: 'vibration' as const, value: telemetry?.vibration ?? null, unit: 'mm/s' },
      { label: 'Battery Voltage', key: 'battery_voltage' as const, value: telemetry?.battery_voltage ?? null, unit: 'V' },
      { label: 'Altitude', key: 'altitude' as const, value: telemetry?.altitude ?? null, unit: 'm' },
      { label: 'Throttle', key: 'throttle' as const, value: telemetry?.throttle ?? null, unit: '%' },
      { label: 'Load', key: 'load' as const, value: telemetry?.load ?? null, unit: '%' },
    ],
    [telemetry],
  );

  const interfaceName = telemetry?.source_interface ?? dataHealth?.can_interface ?? 'vcan0';

  const stageMap: Record<number, string> = {
    0: "OFF", 1: "PRE_FLIGHT", 2: "ENGINE_START", 3: "WARMUP",
    4: "TAXI", 5: "TAKEOFF", 6: "INITIAL_CLIMB", 7: "CLIMB",
    8: "CRUISE_CLIMB", 9: "CRUISE", 10: "HIGH_ALTITUDE_CRUISE",
    11: "LOITER", 12: "DESCENT", 13: "APPROACH", 14: "LANDING",
    15: "COOLDOWN", 16: "SHUTDOWN", 17: "POST_FLIGHT", 18: "MISSION_COMPLETE",
    99: "THROTTLE_TRANSITION"
  };
  const missionStage = stageMap[Math.round(telemetry?.mission_stage ?? 0)] ?? 'UNKNOWN';

  async function handleStartSimulation() {
    try {
      const flight = await createFlight('Simulation Flight', 'surveillance');
      if (flight && flight.flight_id) {
        setActiveFlightId(flight.flight_id);
        const started = await startFlight(flight.flight_id);
        if (started) {
          setSimStatus('RUNNING');
          // Also trigger backend simulator start
          await fetch(`${import.meta.env.VITE_API_URL}/api/simulator/start`, { method: 'POST' });
        }
      }
    } catch (e) {
      setSimStatus('ERROR');
    }
  }

  async function handleStopSimulation() {
    if (!activeFlightId) return;
    try {
      await stopFlight(activeFlightId);
      await fetch(`${import.meta.env.VITE_API_URL}/api/simulator/stop`, { method: 'POST' });
      setActiveFlightId(null);
      setSimStatus('IDLE');
    } catch (e) {
      console.error('Stop error:', e);
    }
  }

  return (
    <div className="app-shell">
      <ConnectionStatus
        connectionState={connectionState}
        backendHealth={backendHealth}
        lastUpdate={lastUpdate}
        interfaceName={interfaceName}
        stale={stale}
        missionStage={missionStage}
      />

      {/* SECTION 1: SIMULATION CONTROL */}
      <section className="simulation-section panel" style={{ marginBottom: '2rem' }}>
        <h2 style={{ marginTop: 0 }}>SIMULATION</h2>
        <div className="sim-controls" style={{ display: 'flex', gap: '2rem', alignItems: 'flex-start' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Flight ID:</strong> {activeFlightId || 'NONE'}</p>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Status:</strong> {simStatus}</p>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Stage:</strong> {missionStage}</p>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Altitude:</strong> {telemetry?.altitude ?? '--'} m</p>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Throttle:</strong> {telemetry?.throttle ?? '--'} %</p>
              <p style={{ margin: 0 }}><strong style={{ color: 'var(--muted)' }}>Load:</strong> {telemetry?.load ?? '--'} %</p>
            </div>
            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <button
                onClick={handleStartSimulation}
                disabled={simStatus === 'RUNNING'}
                style={{ padding: '0.5rem 1rem', background: 'var(--green)', color: '#060b18', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
              >
                START NEW SIMULATION
              </button>
              <button
                onClick={handleStopSimulation}
                disabled={simStatus !== 'RUNNING'}
                style={{ padding: '0.5rem 1rem', background: 'var(--red)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
              >
                STOP SIMULATION
              </button>
            </div>
          </div>
          <MissionTimeline currentStage={missionStage} />
        </div>
        <div className="can-telemetry" style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
          {cards.map(card => (
            <div key={card.label} className="telemetry-card">
              <span style={{ fontSize: '0.8rem', color: 'var(--muted)', display: 'block' }}>{card.label}</span>
              <div style={{ fontWeight: 'bold', fontSize: '1.1rem', color: 'var(--text)' }}>{card.value ?? '--'} {card.unit}</div>
            </div>
          ))}
        </div>
      </section>

      {/* SECTION 2: LIVE FLIGHT DATA */}
      <section className="live-data-section">
        <h2 style={{ borderBottom: '2px solid var(--border)', paddingBottom: '0.5rem' }}>LIVE FLIGHT DATA</h2>
        <EngineStatus telemetry={telemetry} dataHealth={dataHealth} stale={stale} />
        <div className="card-grid">
          {cards.map((card) => (
            <TelemetryCard
              key={card.label}
              label={card.label}
              value={card.value}
              unit={card.unit}
              fresh={getSignalFreshness(dataHealth, card.key)}
              trend={telemetry ? getTrend(history, card.key) : null}
            />
          ))}
        </div>
        <div className="chart-grid">
          <TelemetryChart title="RPM vs Time" history={history} series={[{ key: 'rpm', name: 'RPM', color: '#7dd3fc' }]} />
          <TelemetryChart title="CHT and EGT vs Time" history={history} series={[{ key: 'cht', name: 'CHT', color: '#f97316' }, { key: 'egt', name: 'EGT', color: '#facc15' }]} />
          <TelemetryChart title="Oil Pressure and Oil Temperature vs Time" history={history} series={[{ key: 'oil_pressure', name: 'Oil Pressure (kPa)', color: '#60a5fa' }, { key: 'oil_temperature', name: 'Oil Temperature (°C)', color: '#c084fc' }]} />
          <TelemetryChart title="Fuel Flow and Vibration vs Time" history={history} series={[{ key: 'fuel_flow', name: 'Fuel Flow (L/h)', color: '#34d399' }, { key: 'vibration', name: 'Vibration (mm/s)', color: '#fb7185' }]} />
          <TelemetryChart title="Battery Voltage vs Time" history={history} series={[{ key: 'battery_voltage', name: 'Battery Voltage', color: '#fbbf24' }]} />
        </div>
        <DataHealthPanel dataHealth={dataHealth} />
      </section>

      {/* SECTION 3: FLIGHT HISTORY */}
      <section className="history-section" style={{ marginTop: '3rem', padding: '1rem', borderTop: '2px solid var(--border)' }}>
        <h2 style={{ borderBottom: '2px solid var(--border)', paddingBottom: '0.5rem' }}>FLIGHT HISTORY</h2>
        {flightsLoading ? <p>Loading flights...</p> : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '1rem', fontSize: '0.9rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '2px solid var(--border)', background: 'var(--panel-2)' }}>
                  <th style={{ padding: '0.75rem' }}>Flight ID</th>
                  <th style={{ padding: '0.75rem' }}>Label</th>
                  <th style={{ padding: '0.75rem' }}>Mission</th>
                  <th style={{ padding: '0.75rem' }}>Status</th>
                  <th style={{ padding: '0.75rem' }}>Created At</th>
                </tr>
              </thead>
              <tbody>
                {flights.map(f => (
                  <tr key={f.flight_id} style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => alert(`Loading flight ${f.flight_id}...`)}>
                    <td style={{ padding: '0.75rem' }}>{f.flight_id}</td>
                    <td style={{ padding: '0.75rem' }}>{f.label}</td>
                    <td style={{ padding: '0.75rem' }}>{f.mission_type}</td>
                    <td style={{ padding: '0.75rem' }}>
                      <span style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        background: f.status === 'COMPLETED' ? 'rgba(74, 222, 128, 0.2)' : f.status === 'RUNNING' ? 'rgba(96, 165, 250, 0.2)' : 'rgba(255, 255, 255, 0.1)',
                        color: f.status === 'COMPLETED' ? 'var(--green)' : f.status === 'RUNNING' ? 'var(--blue)' : 'var(--muted)'
                      }}>
                        {f.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem' }}>{new Date(f.created_at).toLocaleString()}</td>
                  </tr>
                ))}
                {flights.length === 0 && <tr><td colSpan={5} style={{ textAlign: 'center', padding: '2rem' }}>No flights found in history.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
