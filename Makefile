PYTHON := python
DB_PATH := Code/data/digital_twin.db
MODEL_OUT := Code/ml/models/anomaly_iforest.pkl

.PHONY: help train-model ensure-db ensure-model-dir

help:
	@echo "Makefile targets:"
	@echo "  make train-model    # Train anomaly model and save to ${MODEL_OUT}"

ensure-model-dir:
	@mkdir -p $(dir ${MODEL_OUT})

ensure-db:
	@echo "Ensuring database exists at $(DB_PATH)"
	@PYTHONPATH=Code python -c "from src.database.database import init_database; init_database()"

train-model: ensure-model-dir ensure-db
	@echo "Training anomaly detector..."
	@PYTHONPATH=Code $(PYTHON) Code/ml/train_baseline.py --db-path $(DB_PATH) --out $(MODEL_OUT)
	@echo "Model written to: $(MODEL_OUT)"
