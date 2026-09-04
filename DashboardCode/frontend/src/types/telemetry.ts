export interface EngineTelemetry {
  timestamp: string;
  rpm: number;
  cht: number;
  egt: number;
  oil_pressure: number;
  oil_temperature: number;
  fuel_flow: number;
  vibration: number;
  battery_voltage: number;
  source_interface: string;
  sequence: number;
}

export interface SignalFreshness {
  fresh: boolean;
  age_ms: number;
  last_seen?: string | null;
}

export interface DataHealth {
  can_interface: 'CONNECTED' | 'DISCONNECTED';
  frames_received: number;
  frames_per_sec: number;
  unknown_frames: number;
  invalid_frames: number;
  signals_total: number;
  signals_fresh: number;
  signal_freshness: Record<string, SignalFreshness>;
  last_update?: string | null;
  latest_sequence: number;
}

export interface BackendHealth {
  ok: boolean;
  can_interface: string;
  backend: string;
  message: string;
}

export type ConnectionState = 'LIVE' | 'DISCONNECTED';
