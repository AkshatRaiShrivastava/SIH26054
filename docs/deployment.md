# Deployment

## Local Linux

```bash
cp .env.example .env
sudo ./deploy/setup_vcan.sh
docker compose up -d --build
```

Open `http://localhost:8080/`.

## AWS EC2

Use Ubuntu 22.04+ and allow SSH plus the selected HTTP port in the EC2 Security Group. The bootstrap script installs Docker, creates persistent `vcan0`, generates environment values, configures UFW, and starts Compose.

```bash
sudo REPO_URL=https://github.com/OWNER/REPOSITORY.git bash deploy/ec2_bootstrap.sh
```

For updates:

```bash
cd /opt/sih/uav-digital-twin
sudo docker compose up -d --build --force-recreate simulator backend user-dashboard landing nginx
```

Rebuild simulator and backend together whenever CAN payload or heartbeat behavior changes.
