type Props = {
  label: string;
  value: number | null;
  unit: string;
  fresh: boolean;
  trend: 'up' | 'down' | 'flat' | null;
};

export function TelemetryCard({ label, value, unit, fresh, trend }: Props) {
  return (
    <article className="telemetry-card">
      <div className="telemetry-header">
        <h3>{label}</h3>
        <span className={`fresh-pill ${fresh ? 'fresh' : 'stale'}`}>{fresh ? '● Fresh' : '● Stale'}</span>
      </div>
      <div className="telemetry-value">
        {value === null ? '--' : value.toFixed(unit === 'rpm' ? 0 : 1)} <span>{unit}</span>
      </div>
      <div className="telemetry-footer">
        <span>Signal freshness</span>
        <span>{trend === 'up' ? '▲' : trend === 'down' ? '▼' : '■'} {fresh ? 'Fresh' : 'Stale'}</span>
      </div>
    </article>
  );
}
