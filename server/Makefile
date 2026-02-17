.PHONY: test lint run dev migrate docker-up docker-down clean

# ─── Dev ───
test:
	PYTHONPATH=src python -m pytest tests/unit/ -v --tb=short

test-all:
	PYTHONPATH=src python -m pytest tests/ -v --tb=short

test-cov:
	PYTHONPATH=src python -m pytest tests/unit/ --cov=pdf_sku --cov-report=term-missing

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

run:
	PYTHONPATH=src uvicorn pdf_sku.main:create_app --factory --host 0.0.0.0 --port 8000

dev:
	PYTHONPATH=src APP_ENV=development uvicorn pdf_sku.main:create_app --factory --reload --reload-dir src

# ─── DB ───
migrate:
	alembic upgrade head

migrate-create:
	alembic revision --autogenerate -m "$(msg)"

# ─── Docker ───
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f app

# ─── Clean ───
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage

# ─── OpenAPI ───
openapi:
	PYTHONPATH=src python -c "from pdf_sku.main import create_app; import json; print(json.dumps(create_app().openapi(), indent=2, ensure_ascii=False))" > openapi.json
	@echo "OpenAPI spec exported to openapi.json"
