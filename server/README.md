# pdf-sku-server

> PDF 自动分类与 SKU 提取系统 — 后端服务 (模块化单体)

## 技术栈

Python 3.11 · FastAPI · SQLAlchemy (async) · PostgreSQL 15 · Redis 7 · MinIO · Gemini/Qwen-VL · Prometheus · Langfuse

## 快速启动

```bash
# 1. 安装
pip install -e ".[dev]"

# 2. 启动基础设施 (需要 pdf-sku-infra)
cd ../pdf-sku-infra && docker compose up -d

# 3. 初始化 DB
alembic upgrade head

# 4. 启动
uvicorn pdf_sku.main:create_app --factory --reload --port 8000
```

## 工程结构

```
src/pdf_sku/
├── common/          # enums(28种) + protocols(11个) + schemas + exceptions
├── config/          # 阈值配置 + impact_preview
├── gateway/         # 上传(TUS) + Job管理 + SSE(9事件) + user_status双轨
├── evaluator/       # 置信度评估 + 路由决策
├── pipeline/        # AI处理管线 (Semaphore并行 + parser→classifier→extractor→binder→exporter)
├── collaboration/   # 任务管理 + auto_pick_next + 标注 + SLA
├── output/          # 增量导入 + 对账 + sync_job
├── feedback/        # 校准 + 升级建议 + few-shot
├── llm_adapter/     # 多模型统一 (client+prompt+parser+resilience)
└── storage/         # 文件存储 (local/minio)
```

## 文档 (`docs/` 目录)

| 文档 | 内容 | 行数 |
|------|------|------|
| data_dictionary_state_machines | 数据字典+状态机 (**开发首查**) | 960 |
| database_ddl_v1_2 | DDL 全量 (17表) | 674 |
| interface_contracts_v1_2 | Protocol 接口契约 (11协议) | 470 |
| openapi_v2_0.yaml | API 规范 (53端点) | 1950 |
| llm_adapter_detailed_design_v1_2 | LLM Adapter 代码级详设 | 2158 |
| technical_architecture_v1_6 | 系统架构 (8 Mermaid图) | 4257 |
| + 12份模块详设/BRD/BA/测试/部署/排期 | | |

## Sprint 分工 (对齐排期 V1.2)

| Sprint | Dev-A | Dev-B | Dev-C |
|--------|-------|-------|-------|
| S0 (W1-2) | DB Migration + enums + protocols | Storage + common DTO | 骨架 + Dockerfile |
| S1 (W3-4) | Config + impact_preview | Gateway + user_status + SSE | LLM Adapter (client+resilience) |
| S2 (W5-6) | LLM Adapter (prompt+parser) | Evaluator + route_reason | Pipeline (parser+classifier) |
| S3 (W7-8) | Pipeline (SKU+orchestrator) | Output + sync_job | Collaboration + auto_pick |
| S4 (W9-10) | batch_skip + Feedback | 全链路集成 | 定时任务+性能 |
| S5 (W11-12) | 运维文档 | Grafana | 发布方案 |
