# Troubleshooting

## Dashboard has no values / heartbeat is `None`

```bash
sudo docker compose up -d --build --force-recreate simulator backend nginx
curl -s http://127.0.0.1:8000/api/health
sudo docker compose logs --tail=100 simulator backend
ip link show vcan0
```

Start a mission before expecting a heartbeat timestamp.

## Blank simulator dataset/environment controls

```bash
curl -i http://127.0.0.1:5001/control/datasets
```

If this works directly but Nginx times out, allow Docker bridge traffic to host ports 5001 and 8000.

## Nginx 502/504

```bash
curl -i http://127.0.0.1:5001/control/datasets
curl -i http://127.0.0.1:8000/api/health
```

If direct calls fail, investigate backend/simulator startup logs. If they work, recreate Nginx and inspect its logs.

## ML stays in warm-up

Wait for 15 telemetry packets from one active mission/environment. At one packet per second, first inference takes about 15 seconds.
