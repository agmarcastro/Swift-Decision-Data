.PHONY: up down seed dev test lint format

up:
	docker compose up -d --wait

down:
	docker compose down -v

seed: up
	pip install -e . --quiet
	python -m ingest.loaders.seed

dev: up
	chainlit run ui/app.py --watch

test:
	pytest tests/ -v

lint:
	ruff check .

format:
	ruff format .
