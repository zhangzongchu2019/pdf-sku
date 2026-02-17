#!/bin/bash
set -e
cd "$(dirname "$0")/../docker"
docker compose down
echo "✅ 开发环境已停止"
