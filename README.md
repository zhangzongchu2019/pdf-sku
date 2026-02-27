# PDF-SKU — PDF 产品目录 SKU 智能提取系统

从 PDF 产品目录中自动识别、提取 SKU 信息并关联产品图片。

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + TypeScript + Zustand + TailwindCSS + Vite |
| 后端 | FastAPI + SQLAlchemy Async + Alembic |
| 数据库 | PostgreSQL 16 |
| 缓存 | Redis 7 |
| 对象存储 | MinIO |
| AI/VLM | Gemini / Qwen / OpenRouter (OpenAI 兼容) |
| 部署 | Docker Compose |

## 前置要求

- **Docker** ≥ 24.0 + Docker Compose V2
- **Python** ≥ 3.11（本地开发模式）
- **Node.js** ≥ 20（本地开发模式）
- **LLM API Key**（至少配置一个: Gemini / Qwen / OpenRouter）
- **磁盘空间** ≥ 2GB（用于 DocLayout-YOLO 模型、PyTorch 依赖、图片缓存）

## 快速开始

### 方式一: 一键启动（推荐）

```bash
git clone <repo-url> pdf-sku && cd pdf-sku

# 完整搭建: 基础设施 + 后端 + 前端 (开发模式, 支持热重载)
./setup.sh

# 编辑 LLM API Key (首次必须)
vim server/.env
```

脚本会自动完成: Docker 基础设施启动 → Python venv 创建 → 依赖安装 → 数据库迁移 → 前后端启动。

### 方式二: Docker 全栈部署

```bash
git clone <repo-url> pdf-sku && cd pdf-sku

# 构建镜像并启动所有服务
./setup.sh --docker

# 编辑 LLM API Key
vim server/.env
# 重启后端使配置生效
docker compose -f infra/docker/docker-compose.yml restart server
```

访问 http://localhost (前端) / http://localhost:8000/docs (API 文档)

### 方式三: 手动搭建

```bash
# 1. 启动基础设施
cd infra/docker && docker compose up -d postgres redis minio

# 2. 后端
cd server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # 编辑填写 LLM API Key
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn "pdf_sku.main:create_app" --factory --host 0.0.0.0 --port 8000 --reload

# 3. 前端 (另一个终端)
cd web
cp .env.example .env
npm install && npm run dev
```

## setup.sh 命令参考

```bash
./setup.sh              # 完整搭建 (基础设施 + 后端 + 前端)
./setup.sh --infra      # 只启动基础设施 (PG/Redis/MinIO)
./setup.sh --docker     # Docker 全栈部署 (含构建镜像)
./setup.sh --stop       # 停止所有 Docker 服务
./setup.sh --reset      # 清除数据重建 (慎用, 会删除数据库)
```

## LLM 配置

编辑 `server/.env`，至少配置一个 LLM Provider:

```bash
# Gemini (推荐, 性价比最优)
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
DEFAULT_LLM_CLIENT=gemini

# 如需中转代理
GEMINI_API_BASE=https://your-proxy.com

# Qwen (阿里云)
QWEN_API_KEY=your-key
QWEN_MODEL=qwen-vl-max

# OpenRouter (支持多模型)
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=google/gemini-2.5-flash
```

## 项目结构

```
pdf-sku/
├── server/                  # 后端
│   ├── src/pdf_sku/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── common/          # 数据模型、配置
│   │   ├── gateway/         # API 路由
│   │   └── pipeline/        # 9 阶段处理管线
│   │       ├── parser/      # Phase 1: PDF 解析
│   │       ├── layout_detector.py  # Phase 2c: 合成大图布局检测 (DocLayout-YOLO)
│   │       ├── classifier/  # Phase 5: 页面分类
│   │       ├── extractor/   # Phase 6: SKU 提取
│   │       ├── binder/      # Phase 8: SKU-图片绑定
│   │       └── exporter/    # Phase 9: 导出
│   ├── models/              # YOLO 模型文件 (git ignored, setup.sh 自动下载)
│   ├── alembic/             # 数据库迁移
│   ├── Dockerfile
│   └── .env.example
├── web/                     # 前端
│   ├── src/
│   │   ├── components/      # React 组件
│   │   ├── routes/          # 页面路由
│   │   ├── stores/          # Zustand 状态管理
│   │   └── types/           # TypeScript 类型
│   ├── Dockerfile → infra/docker/Dockerfile.web
│   └── .env.example
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml      # 全栈编排
│   │   └── docker-compose.test.yml # 测试环境
│   └── scripts/
│       ├── init-db.sql      # 数据库初始化
│       ├── start-dev.sh     # 开发环境启动
│       └── stop-dev.sh      # 停止
├── setup.sh                 # 一键搭建脚本
└── README.md
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 (dev) | 5173 | Vite 开发服务器 |
| 前端 (docker) | 80 | Nginx |
| 后端 API | 8000 | FastAPI |
| PostgreSQL | 5432 | pdfsku / pdfsku |
| Redis | 6379 | |
| MinIO API | 9000 | minioadmin / minioadmin |
| MinIO Console | 9001 | 管理界面 |

## 常用操作

```bash
# 数据库迁移
cd server && .venv/bin/python -m alembic upgrade head

# 重跑单个 Job
curl -X POST http://localhost:8000/api/v1/ops/jobs/{job_id}/reprocess-ai

# 重跑单页
curl -X POST http://localhost:8000/api/v1/ops/jobs/{job_id}/reprocess-page/{page_no}

# 查看 Docker 日志
docker compose -f infra/docker/docker-compose.yml logs -f server

# 手动安装布局检测依赖 (setup.sh 会自动执行)
cd server
.venv/bin/pip install doclayout-yolo ultralytics
# 下载 DocLayout-YOLO 模型 (~40MB)
mkdir -p models && wget -O models/doclayout_yolo.pt \
  "https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench/resolve/main/doclayout_yolo_docstructbench_imgsz1024.pt"
```
