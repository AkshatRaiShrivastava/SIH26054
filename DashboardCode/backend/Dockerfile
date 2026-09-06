FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SocketCAN and psycopg
RUN apt-get update && apt-get install -y \
    iproute2 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Start the backend as root to allow access to /var/run/docker.sock
CMD ["python", "-m", "backend.app"]
