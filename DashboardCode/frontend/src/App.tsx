import { useMemo } from 'react';
import { ConnectionStatus } from './components/ConnectionStatus';
import { DataHealthPanel } from './components/DataHealth';
import { EngineStatus } from './components/EngineStatus';
import { TelemetryCard } from './components/TelemetryCard';
import { TelemetryChart } from './components/TelemetryChart';
import { useTelemetry } from './hooks/useTelemetry';
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
];

function getSignalFreshness(dataHealth: DataHealth | null, key: keyof EngineTelemetry) {
  return dataHealth?.signal_freshness?.[String(key)]?.fresh ?? false;
}

function getTrend(history: EngineTelemetry[], key: keyof EngineTelemetry) {
  if (history.length < 2) {
    return null;
  }
  const previous = history[history.length - 2][key] as number;
  const current = history[history.length - 1][key] as number;
  if (current > previous) return 'up' as const;
  if (current < previous) return 'down' as const;
  return 'flat' as const;
}

export default function App() {
  const { telemetry, history, dataHealth, backendHealth, connectionState, lastUpdate, stale } = useTelemetry();

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
    ],
    [telemetry],
  );

  const interfaceName = telemetry?.source_interface ?? dataHealth?.can_interface ?? 'vcan0';

  return (
    <div className="app-shell">
      <ConnectionStatus
        connectionState={connectionState}
        backendHealth={backendHealth}
        lastUpdate={lastUpdate}
        interfaceName={interfaceName}
        stale={stale}
      />

      <EngineStatus telemetry={telemetry} dataHealth={dataHealth} stale={stale} />

      <section className="card-grid">
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
      </section>

      <section className="chart-grid">
        <TelemetryChart title="RPM vs Time" history={history} series={[{ key: 'rpm', name: 'RPM', color: '#7dd3fc' }]} />
        <TelemetryChart title="CHT and EGT vs Time" history={history} series={[{ key: 'cht', name: 'CHT', color: '#f97316' }, { key: 'egt', name: 'EGT', color: '#facc15' }]} />
        <TelemetryChart title="Oil Pressure and Oil Temperature vs Time" history={history} series={[{ key: 'oil_pressure', name: 'Oil Pressure (kPa)', color: '#60a5fa' }, { key: 'oil_temperature', name: 'Oil Temperature (°C)', color: '#c084fc' }]} />
        <TelemetryChart title="Fuel Flow and Vibration vs Time" history={history} series={[{ key: 'fuel_flow', name: 'Fuel Flow (L/h)', color: '#34d399' }, { key: 'vibration', name: 'Vibration (mm/s)', color: '#fb7185' }]} />
        <TelemetryChart title="Battery Voltage vs Time" history={history} series={[{ key: 'battery_voltage', name: 'Battery Voltage', color: '#fbbf24' }]} />
      </section>

      <DataHealthPanel dataHealth={dataHealth} />
    </div>
  );
}
