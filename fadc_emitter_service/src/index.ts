import express, { Request, Response } from "express";
import { Server as WebSocketServer } from "ws";
import http from "http";
import crypto from "crypto";

/**
 * In‑memory mission state and configuration.
 */
interface MissionConfig {
  durationSec?: number; // optional mission duration
  startedAt?: number; // epoch ms when mission started
  running: boolean;
  fault?: string; // simple fault identifier
}

const mission: MissionConfig = {
  running: false,
};

/**
 * Simple AR(1) noise generator used for telemetry values.
 */
class AR1Noise {
  private prev: number;
  constructor(private readonly phi: number = 0.9, private readonly sigma: number = 0.1) {
    this.prev = Math.random();
  }
  next(): number {
    const eps = this.sigma * (Math.random() - 0.5) * 2; // uniform approx normal
    this.prev = this.phi * this.prev + eps;
    return this.prev;
  }
}

const noiseGen = new AR1Noise();

/**
 * AES‑256‑GCM encryption helper. The key is read from the environment variable
 * FADEC_CAN_KEY as a base64‑encoded 32‑byte key.
 */
function encryptTelemetry(plain: string): string {
  const keyB64 = process.env.FADEC_CAN_KEY;
  if (!keyB64) {
    throw new Error("FADEC_CAN_KEY environment variable not set");
  }
  // The original scripts generate a 64‑character hex string (32 bytes).
  // Accept either a base64‑encoded 32‑byte key or a hex string.
  let key: Buffer;
  if (/^[0-9a-fA-F]{64}$/.test(keyB64)) {
    // Hex representation
    key = Buffer.from(keyB64, "hex");
  } else {
    // Assume base64
    key = Buffer.from(keyB64, "base64");
  }
  if (key.length !== 32) {
    throw new Error("FADEC_CAN_KEY must represent 32 bytes (hex 64 chars or base64)");
  }
  const iv = crypto.randomBytes(12); // 96‑bit nonce recommended for GCM
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([cipher.update(plain, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  // Encode as base64 JSON for transport
  const payload = {
    iv: iv.toString("base64"),
    data: ciphertext.toString("base64"),
    tag: tag.toString("base64"),
  };
  return JSON.stringify(payload);
}

/**
 * Broadcast a message to all connected WebSocket clients.
 */
function broadcast(wsServer: WebSocketServer, type: string, payload: any) {
  const message = JSON.stringify({ type, payload });
  wsServer.clients.forEach((client) => {
    if (client.readyState === client.OPEN) {
      client.send(message);
    }
  });
}

/**
 * Generate a telemetry frame. The structure mirrors the original Python version
 * but is simplified for demonstration purposes.
 */
function generateTelemetry(): string {
  const telemetry = {
    timestamp: Date.now(),
    // Example sensor values with noise
    rpm: 2500 + noiseGen.next() * 100,
    temperature: 85 + noiseGen.next() * 5,
    pressure: 101.3 + noiseGen.next() * 0.5,
    fault: mission.fault || null,
  };
  const plain = JSON.stringify(telemetry);
  return encryptTelemetry(plain);
}

/**
 * Main server setup.
 */
const app = express();
app.use(express.json());

// REST control endpoints
app.post("/control/start-mission", (req: Request, res: Response) => {
  if (mission.running) {
    return res.status(400).json({ error: "Mission already running" });
  }
  const { durationSec } = req.body as { durationSec?: number };
  mission.running = true;
  mission.startedAt = Date.now();
  mission.durationSec = durationSec;
  res.json({ status: "started", durationSec });
});

app.post("/control/stop-mission", (_: Request, res: Response) => {
  mission.running = false;
  mission.startedAt = undefined;
  mission.durationSec = undefined;
  res.json({ status: "stopped" });
});

app.post("/control/fault", (req: Request, res: Response) => {
  const { fault } = req.body as { fault: string };
  if (!fault) {
    return res.status(400).json({ error: "fault field required" });
  }
  mission.fault = fault;
  res.json({ status: "fault set", fault });
});

app.post("/control/fault/clear", (_: Request, res: Response) => {
  mission.fault = undefined;
  res.json({ status: "fault cleared" });
});

app.get("/control/status", (_: Request, res: Response) => {
  res.json({ running: mission.running, fault: mission.fault ?? null });
});

// Health endpoint for Vercel / monitoring
app.get("/health", (_: Request, res: Response) => {
  res.json({ ok: true });
});

// HTTP server needed for WebSocket upgrade
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/ws" });

// Periodic telemetry broadcast (10 Hz)
const TELEMETRY_INTERVAL_MS = 100;
let telemetryTimer: NodeJS.Timeout | null = null;

function startTelemetryLoop() {
  if (telemetryTimer) return;
  telemetryTimer = setInterval(() => {
    if (!mission.running) return;
    // Stop after duration if set
    if (mission.durationSec && mission.startedAt) {
      const elapsedSec = (Date.now() - mission.startedAt) / 1000;
      if (elapsedSec >= mission.durationSec) {
        mission.running = false;
        clearInterval(telemetryTimer as NodeJS.Timeout);
        telemetryTimer = null;
        broadcast(wss, "mission_end", {});
        return;
      }
    }
    const encrypted = generateTelemetry();
    broadcast(wss, "telemetry", { data: encrypted });
    // Heartbeat every second (simple implementation)
    if (Date.now() % 1000 < TELEMETRY_INTERVAL_MS) {
      broadcast(wss, "heartbeat", { timestamp: Date.now() });
    }
    // Fault event broadcast when fault is present
    if (mission.fault) {
      broadcast(wss, "fault_event", { fault: mission.fault, timestamp: Date.now() });
    }
  }, TELEMETRY_INTERVAL_MS);
}

// Start telemetry loop when server starts – it will emit only when mission.running
startTelemetryLoop();

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`FADEC emitter service listening on port ${PORT}`);
});
