#!/bin/bash
# CI/CD: 部署到 K8s
set -e
ENV=${1:-dev}
TAG=${2:-latest}
REGISTRY=${REGISTRY:-"registry.internal"}

echo "=== Deploying to ${ENV} with tag ${TAG} ==="

cd "$(dirname "$0")/../k8s/overlays/${ENV}"

# 更新镜像 tag
kustomize edit set image \
  pdf-sku-server=${REGISTRY}/pdf-sku-server:${TAG} \
  pdf-sku-web=${REGISTRY}/pdf-sku-web:${TAG}

kubectl apply -k .

echo "=== Waiting for rollout ==="
kubectl -n pdf-sku rollout status deployment/pdf-sku-server --timeout=300s
kubectl -n pdf-sku rollout status deployment/pdf-sku-web --timeout=120s

echo "=== Deploy complete ==="
