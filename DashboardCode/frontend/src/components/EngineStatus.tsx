import { monitoringThresholds } from '../config/thresholds';
import type { DataHealth, EngineTelemetry } from '../types/telemetry';

type Props = {
  telemetry: EngineTelemetry | null;
  dataHealth: DataHealth | null;
  stale: boolean;
};

function getAlerts(telemetry: EngineTelemetry | null) {
  if (!telemetry) return [];
  return [
    telemetry.cht > monitoringThresholds.chtHighC && `High CHT (${telemetry.cht.toFixed(1)} °C)`,
    telemetry.egt > monitoringThresholds.egtHighC && `High EGT (${telemetry.egt.toFixed(1)} °C)`,
    telemetry.oil_pressure < monitoringThresholds.oilPressureLowKpa && `Low oil pressure (${telemetry.oil_pressure.toFixed(1)} kPa)`,
    telemetry.oil_temperature > monitoringThresholds.oilTemperatureHighC && `High oil temperature (${telemetry.oil_temperature.toFixed(1)} °C)`,
    telemetry.fuel_flow > monitoringThresholds.fuelFlowHighLph && `High fuel flow (${telemetry.fuel_flow.toFixed(1)} L/h)`,
    telemetry.vibration > monitoringThresholds.vibrationHighMms && `High vibration (${telemetry.vibration.toFixed(2)} mm/s)`,
    telemetry.battery_voltage < monitoringThresholds.batteryLowV && `Low battery (${telemetry.battery_voltage.toFixed(1)} V)`,
  ].filter((alert): alert is string => Boolean(alert));
}

function getStatus(telemetry: EngineTelemetry | null, alertCount: number) {
  if (!telemetry) {
    return { label: 'WAITING', tone: 'muted' as const, health: 0 };
  }

  if (alertCount >= 2) {
    return { label: 'CRITICAL', tone: 'critical' as const, health: 55 };
  }
  if (alertCount === 1) {
    return { label: 'CAUTION', tone: 'caution' as const, health: 72 };
  }
  return { label: 'NORMAL', tone: 'normal' as const, health: 100 };
}

export function EngineStatus({ telemetry, dataHealth, stale }: Props) {
  const alerts = getAlerts(telemetry);
  const status = getStatus(telemetry, alerts.length);
  const freshSignals = dataHealth?.signals_fresh ?? 0;
  const totalSignals = dataHealth?.signals_total ?? 8;

  return (
    <section className="panel status-panel">
      <div className="panel-heading inline-heading">
        <h2>ENGINE STATUS</h2>
        <div className={`status-badge ${status.tone}`}>{status.label}</div>
      </div>
      <div className="status-metrics">
        <div>
          <div className="label">Health</div>
          <div className="value-large">{status.health}%</div>
        </div>
        <div>
          <div className="label">Data Quality</div>
          <div className="value-large">
            {freshSignals}/{totalSignals} fresh
          </div>
        </div>
        <div>
          <div className="label">CAN</div>
          <div className="value-large">{dataHealth?.can_interface ?? 'DISCONNECTED'}</div>
        </div>
        <div>
          <div className="label">RX</div>
          <div className="value-large">{dataHealth ? `${dataHealth.frames_per_sec.toFixed(1)} fps` : '0.0 fps'}</div>
        </div>
      </div>
      <div className={`fault-alerts ${alerts.length ? status.tone : 'normal'}`}>
        <div className="label">Sensor-derived fault alerts</div>
        {alerts.length ? alerts.join(' · ') : 'No threshold violations detected'}
      </div>
      <div className="small-note">{stale ? 'Signal stream is stale.' : 'Signal stream is live.'}</div>
    </section>
  );
}
