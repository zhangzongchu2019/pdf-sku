#!/bin/bash
# 重置数据库 (删除所有数据)
set -e
cd "$(dirname "$0")/../docker"
echo "⚠️ 即将删除所有数据库数据！"
read -p "确认? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  docker compose down -v
  docker compose up -d postgres redis
  echo "等待 PostgreSQL 启动..."
  sleep 5
  cd "$(dirname "$0")/../../pdf-sku-server"
  PYTHONPATH=src alembic upgrade head 2>/dev/null || echo "迁移跳过"
  echo "✅ 数据库已重置"
fi
