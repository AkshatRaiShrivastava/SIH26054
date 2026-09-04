PYTHON ?= python3
NPM ?= npm

SIMULATOR_DIR := uav-engine-digital-twin
BACKEND_DIR := DashboardCode/backend
FRONTEND_DIR := DashboardCode/frontend

.DEFAULT_GOAL := help
.PHONY: help install db-up db-down can-up can-down simulator backend frontend dev generate-data generate-ideal-flights check build

help:
	@echo "UAV Engine Digital Twin — commands"
	@echo "  make install     Install Python and frontend dependencies"
	@echo "  make db-up       Start the project PostgreSQL database with Docker"
	@echo "  make db-down     Stop the project PostgreSQL database"
	@echo "  make can-up      Create the local vcan0 CAN interface (Linux; may ask for sudo)"
	@echo "  make dev         Run simulator + CAN receiver/API + React dashboard in one terminal"
	@echo "  make simulator   Run only the CAN simulator"
	@echo "  make backend     Run only the CAN receiver and API on :8000"
	@echo "  make frontend    Run only the React dashboard on :5173"
	@echo "  make generate-data  Create labelled PostgreSQL ML training data"
	@echo "  make generate-ideal-flights  Create ideal no-fault flight time series in PostgreSQL"
	@echo "  make check       Run Python tests and frontend type checks"
	@echo "  make build       Create the production frontend build"
	@echo "  make can-down    Remove vcan0 (only if this project created it)"

install:
	$(PYTHON) -m pip install -r $(SIMULATOR_DIR)/requirements.txt -r $(BACKEND_DIR)/requirements.txt
	$(NPM) --prefix $(FRONTEND_DIR) ci

db-up:
	@docker compose up -d

db-down:
	@docker compose down

can-up:
	@./scripts/can-interface.sh up

can-down:
	@./scripts/can-interface.sh down

simulator:
	@cd $(SIMULATOR_DIR) && $(PYTHON) main.py --interface $${CAN_INTERFACE:-vcan0} $(SIMULATOR_ARGS)

backend:
	@cd DashboardCode && $(PYTHON) -m backend.app --interface $${CAN_INTERFACE:-vcan0}

frontend:
	@$(NPM) --prefix $(FRONTEND_DIR) run dev -- --host 0.0.0.0

dev:
	@SIMULATOR_ARGS="$(SIMULATOR_ARGS)" $(PYTHON) scripts/dev.py

generate-data:
	@$(PYTHON) scripts/generate_training_data.py $(DATA_ARGS)

generate-ideal-flights:
	@$(PYTHON) scripts/generate_ideal_flights.py $(IDEAL_FLIGHT_ARGS)

check:
	@cd $(SIMULATOR_DIR) && $(PYTHON) -m pytest
	@cd DashboardCode && $(PYTHON) -m pytest backend/tests
	@$(NPM) --prefix $(FRONTEND_DIR) run typecheck

build:
	@$(NPM) --prefix $(FRONTEND_DIR) run build
