import type { BackendHealth, ConnectionState } from '../types/telemetry';

type Props = {
  connectionState: ConnectionState;
  backendHealth: BackendHealth | null;
  lastUpdate: string | null;
  interfaceName: string;
  stale: boolean;
};

export function ConnectionStatus({ connectionState, backendHealth, lastUpdate, interfaceName, stale }: Props) {
  const liveColor = connectionState === 'LIVE' ? 'var(--green)' : 'var(--red)';
  return (
    <section className="panel connection-panel">
      <div className="panel-heading">
        <h2>UAV ENGINE DIGITAL TWIN</h2>
        <div className="status-row">
          <span className="status-pill" style={{ color: liveColor }}>
            ● {connectionState}
          </span>
          <span className="status-pill">Data: {connectionState}</span>
          <span className="status-pill">Interface: {interfaceName}</span>
        </div>
      </div>
      <div className="connection-grid">
        <div>
          <div className="label">Connection</div>
          <div className="value-large">{backendHealth?.can_interface ?? 'DISCONNECTED'}</div>
        </div>
        <div>
          <div className="label">Last Update</div>
          <div className="value-large">{lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : 'Waiting...'}</div>
        </div>
        <div>
          <div className="label">Stale</div>
          <div className="value-large">{stale ? 'Yes' : 'No'}</div>
        </div>
      </div>
    </section>
  );
}
