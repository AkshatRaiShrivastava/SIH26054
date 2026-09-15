#!/usr/bin/env bash

# Helper script to launch the Engine Simulator Flask UI.
# It activates the project's virtual environment, then runs the Flask app
# located at EngineSimulator/frontend/app.py.

VENV_DIR="$(dirname "$0")/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found at $VENV_DIR. Create it first with 'python3 -m venv .venv' and install dependencies."
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Export Flask environment variables for development mode
export FLASK_APP=EngineSimulator.frontend.app
export FLASK_ENV=development

# Run the Flask development server on port 5000 (default)
flask run --host 0.0.0.0 --port 5000