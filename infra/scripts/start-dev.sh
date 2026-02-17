#!/bin/bash
# 启动本地开发环境
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== 启动基础设施 ==="
cd "$ROOT_DIR/docker"
docker compose up -d postgres redis minio

echo "=== 等待服务就绪 ==="
sleep 5
until docker compose exec -T postgres pg_isready -U pdfsku > /dev/null 2>&1; do
  echo "  等待 PostgreSQL..."
  sleep 2
done
echo "  ✅ PostgreSQL 就绪"

until docker compose exec -T redis redis-cli ping > /dev/null 2>&1; do
  echo "  等待 Redis..."
  sleep 2
done
echo "  ✅ Redis 就绪"

echo ""
echo "=== 运行数据库迁移 ==="
cd "$ROOT_DIR/../pdf-sku-server"
PYTHONPATH=src alembic upgrade head 2>/dev/null || echo "  ⚠️ 迁移跳过 (可能未初始化)"

echo ""
echo "=== 启动后端 ==="
PYTHONPATH=src DATABASE_URL="postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku" \
  REDIS_URL="redis://localhost:6379/0" \
  MINIO_ENDPOINT="localhost:9000" \
  APP_ENV=development \
  uvicorn pdf_sku.main:create_app --factory --reload --port 8000 &
SERVER_PID=$!

echo ""
echo "=== 启动前端 ==="
cd "$ROOT_DIR/../pdf-sku-web"
npm run dev &
WEB_PID=$!

echo ""
echo "════════════════════════════════════"
echo "  PDF-SKU 开发环境已启动"
echo "  后端: http://localhost:8000"
echo "  前端: http://localhost:5173"
echo "  PG:   localhost:5432"
echo "  Redis: localhost:6379"
echo "  MinIO: localhost:9000 (console: 9001)"
echo "════════════════════════════════════"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $SERVER_PID $WEB_PID 2>/dev/null; cd $ROOT_DIR/docker && docker compose stop" EXIT
wait
