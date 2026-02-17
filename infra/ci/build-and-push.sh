#!/bin/bash
# CI/CD: 构建并推送 Docker 镜像
set -e

REGISTRY=${REGISTRY:-"registry.internal"}
TAG=${TAG:-$(git rev-parse --short HEAD)}

echo "=== Building pdf-sku-server:${TAG} ==="
docker build -t ${REGISTRY}/pdf-sku-server:${TAG} ../pdf-sku-server/
docker push ${REGISTRY}/pdf-sku-server:${TAG}

echo "=== Building pdf-sku-web:${TAG} ==="
docker build -t ${REGISTRY}/pdf-sku-web:${TAG} ../pdf-sku-web/
docker push ${REGISTRY}/pdf-sku-web:${TAG}

echo "=== Done: images pushed with tag ${TAG} ==="
