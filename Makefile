PYTHON ?= python3
NPM ?= npm

# Docker Compose commands
UP = docker compose up --build
DOWN = docker compose down
DOWN_VOL = docker compose down -v
LOGS = docker compose logs -f

.DEFAULT_GOAL := help
.PHONY: help up down down-vol logs clean install check build

help:
	@echo "UAV Engine Digital Twin — Dockerized Workflow"
	@echo "  make up         Start entire system (DB, CAN, Backend, Sim, Frontend)"
	@echo "  make down       Stop all services"
	@echo "  make down-vol   Stop all services and delete database data"
	@echo "  make logs       Follow container logs"
	@echo "  make clean      Remove all docker volumes and images"
	@echo "  make install     Install local dependencies (only for non-docker dev)"
	@echo "  make check       Run tests inside containers"
	@echo "  make build       Build production frontend"

up:
	$(UP)

down:
	$(DOWN)

down-vol:
	$(DOWN_VOL)

logs:
	$(LOGS)

clean:
	$(DOWN_VOL)
	docker image prune -f

install:
	$(PYTHON) -m pip install -r uav-engine-digital-twin/requirements.txt -r DashboardCode/backend/requirements.txt
	$(NPM) --prefix DashboardCode/frontend ci

check:
	docker compose exec backend pytest tests
	docker compose exec simulator pytest tests

build:
	docker compose exec frontend npm run build
