# PDF-SKU Infrastructure

PDF-SKU 提取系统的基础设施配置。

## 目录结构

```
├── .github/workflows/     CI/CD Pipelines
│   ├── ci.yml             完整 CI (测试→构建→部署)
│   └── infra-validate.yml K8s/Compose 校验
├── ci/                    构建/部署脚本
│   ├── build-and-push.sh  Docker 镜像构建推送
│   └── deploy.sh          K8s 部署
├── docker/                Docker Compose 配置
│   ├── docker-compose.yml 本地开发全栈
│   ├── docker-compose.test.yml  测试环境
│   ├── Dockerfile.web     前端 Nginx 镜像
│   └── nginx.conf         Nginx SPA + API 代理
├── k8s/                   Kubernetes 清单
│   ├── base/              基础配置 (Kustomize)
│   └── overlays/          环境覆盖 (dev/prod)
├── monitoring/            监控配置
│   ├── prometheus/        Prometheus 抓取规则
│   ├── alerting/          告警规则 (15 条)
│   └── grafana/           Grafana Dashboard JSON
├── scripts/               运维脚本
│   ├── start-dev.sh       一键启动开发环境
│   ├── stop-dev.sh        停止开发环境
│   ├── reset-db.sh        重置数据库
│   └── init-db.sql        初始化 SQL
└── docs/                  设计文档
```

## 快速开始

```bash
# 一键启动开发环境
./scripts/start-dev.sh

# 或手动启动
cd docker && docker compose up -d
cd ../pdf-sku-server && make dev
cd ../pdf-sku-web && npm run dev
```

## 部署

```bash
# CI 构建
bash ci/build-and-push.sh

# 部署到 staging
bash ci/deploy.sh staging <git-sha>

# 部署到 production
bash ci/deploy.sh prod <git-sha>
```

## 监控

- Prometheus: 12 个 scrape targets
- Grafana: 12 个 panel (RPS, 错误率, 延迟, 队列深度, LLM...)
- Alerts: 15 条规则覆盖可用性/Pipeline/LLM/标注/导入/基础设施
