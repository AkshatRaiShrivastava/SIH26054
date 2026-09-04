import type { DataHealth } from '../types/telemetry';

type Props = {
  dataHealth: DataHealth | null;
};

export function DataHealthPanel({ dataHealth }: Props) {
  const freshness = Object.entries(dataHealth?.signal_freshness ?? {});
  return (
    <section className="panel data-health-panel">
      <div className="panel-heading inline-heading">
        <h2>DATA HEALTH</h2>
      </div>
      <div className="health-grid">
        <div><span className="label">CAN Interface</span><div className="value-large">{dataHealth?.can_interface ?? 'DISCONNECTED'}</div></div>
        <div><span className="label">Frames Received</span><div className="value-large">{dataHealth?.frames_received ?? 0}</div></div>
        <div><span className="label">Frames/sec</span><div className="value-large">{dataHealth?.frames_per_sec?.toFixed(1) ?? '0.0'}</div></div>
        <div><span className="label">Unknown Frames</span><div className="value-large">{dataHealth?.unknown_frames ?? 0}</div></div>
        <div><span className="label">Invalid Frames</span><div className="value-large">{dataHealth?.invalid_frames ?? 0}</div></div>
        <div><span className="label">Signals Fresh</span><div className="value-large">{dataHealth?.signals_fresh ?? 0} / {dataHealth?.signals_total ?? 8}</div></div>
      </div>
      <div className="freshness-list">
        {freshness.map(([name, item]) => (
          <div key={name} className={`freshness-row ${item.fresh ? 'fresh' : 'stale'}`}>
            <span>{name.replace('_', ' ')}</span>
            <span>{item.fresh ? 'Fresh' : 'Stale'}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
