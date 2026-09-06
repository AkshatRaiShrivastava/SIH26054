FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for SocketCAN
RUN apt-get update && apt-get install -y \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The simulator is started by the backend via Docker API or a trigger.
# For now, we set a default command that keeps the container alive
# or runs a default mission.
CMD ["python", "main.py", "--mission", "surveillance"]
