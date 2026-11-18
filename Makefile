PY ?= python
export PYTHONPATH := src:.

.PHONY: install test lint eval heldout report model image api web

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src evals world tests scripts
	$(PY) -m mypy

eval:
	$(PY) -m evals.run

heldout:
	$(PY) -m evals.run --heldout

report:
	$(PY) -m evals.readme
	$(PY) -m evals.console_data

model:
	$(PY) scripts/build_model.py artefacts

image: model
	docker build -t relevance-scorer:latest .

api:
	MODEL_DIR=artefacts uvicorn screening.serving.app:app --port 8080

web:
	cd web && npm install && npm run dev
