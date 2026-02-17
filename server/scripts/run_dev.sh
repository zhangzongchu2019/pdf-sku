#!/bin/bash
set -e
echo "=== Running migrations ==="
alembic upgrade head
echo "=== Starting dev server ==="
uvicorn pdf_sku.main:create_app --factory --reload --host 0.0.0.0 --port 8000
