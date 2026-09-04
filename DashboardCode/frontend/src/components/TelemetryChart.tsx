import type { EngineTelemetry } from '../types/telemetry';

type SeriesConfig = {
  key: keyof EngineTelemetry;
  name: string;
  color: string;
};

type Props = {
  title: string;
  history: EngineTelemetry[];
  series: SeriesConfig[];
};

function scale(value: number, min: number, max: number, height: number) {
  if (max === min) return height / 2;
  return height - ((value - min) / (max - min)) * height;
}

export function TelemetryChart({ title, history, series }: Props) {
  const width = 1000;
  const height = 260;
  const padding = 20;
  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;
  const data = history.slice(-600);

  const allValues = series.flatMap((item) => data.map((point) => Number(point[item.key])));
  const minValue = allValues.length ? Math.min(...allValues) : 0;
  const maxValue = allValues.length ? Math.max(...allValues) : 1;
  const step = data.length > 1 ? innerWidth / (data.length - 1) : innerWidth;

  return (
    <section className="panel chart-panel">
      <div className="panel-heading inline-heading">
        <h2>{title}</h2>
      </div>
      <div className="chart-wrap">
        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label={title}>
          <rect x="0" y="0" width={width} height={height} rx="14" fill="#0b1327" opacity="0.75" />
          {[0, 1, 2, 3].map((tick) => (
            <line
              key={tick}
              x1={padding}
              x2={width - padding}
              y1={padding + (innerHeight / 3) * tick}
              y2={padding + (innerHeight / 3) * tick}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
            />
          ))}
          {series.map((item) => {
            const points = data
              .map((point, index) => {
                const x = padding + step * index;
                const value = Number(point[item.key]);
                const y = padding + scale(value, minValue, maxValue, innerHeight);
                return `${x},${y}`;
              })
              .join(' ');

            return (
              <polyline
                key={String(item.key)}
                fill="none"
                stroke={item.color}
                strokeWidth="2.5"
                points={points}
              />
            );
          })}
        </svg>
        <div className="chart-legend">
          {series.map((item) => (
            <span key={String(item.key)} className="legend-item">
              <span className="legend-dot" style={{ backgroundColor: item.color }} />
              {item.name}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
