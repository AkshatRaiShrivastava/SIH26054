#!/usr/bin/env bash
set -e

# Move to project root, no matter where script is called from
cd "$(dirname "$0")"

# Activate the project's venv
VENV_DIR=".venv"
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
else
    echo "Virtual environment not found - create it first: python3 -m venv .venv"
    exit 1
fi

# Ensure the encryption key exists
if [ -z "$FADEC_CAN_KEY" ]; then
    FADEC_CAN_KEY=$(python - <<'PY'
import secrets, sys
sys.stdout.write(secrets.token_hex(32))
PY
)
    export FADEC_CAN_KEY
    # Write the key to a file so that the FADEC script can read it
    echo "$FADEC_CAN_KEY" > ".fadec_key"
fi

# Use the virtual CAN bus for inter-process traffic (no setup required)
export CAN_BACKEND=virtual
export CAN_CHANNEL=uav-fadec

# Optional: point the backend at a PostgreSQL DB (not used by the new Node service)
# export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/uav"

# The original Python FastAPI backend has been removed. If you need a backend,
# start the new FADEC emitter service instead:
#   cd fadc_emitter_service && npm install && npm run dev