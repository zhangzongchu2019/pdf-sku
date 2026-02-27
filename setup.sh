#!/usr/bin/env bash
#
# PDF-SKU 开发环境一键搭建脚本
#
# 用法:
#   ./setup.sh              # 完整搭建 (基础设施 + 后端 + 前端)
#   ./setup.sh --infra      # 只启动基础设施 (PG/Redis/MinIO)
#   ./setup.sh --docker     # Docker 全栈部署 (含构建镜像)
#   ./setup.sh --stop       # 停止所有服务
#   ./setup.sh --reset      # 清除数据重建 (慎用)
#
set -euo pipefail

# ── 颜色 ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ── 路径 ──
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_DIR="$ROOT_DIR/server"
WEB_DIR="$ROOT_DIR/web"
INFRA_DIR="$ROOT_DIR/infra"
COMPOSE_FILE="$INFRA_DIR/docker/docker-compose.yml"
VENV="${HOME}/envs/pdf"

# ── 前置检查 ──
check_prerequisites() {
    info "检查前置依赖..."

    command -v docker >/dev/null 2>&1 || fail "需要 Docker, 请安装: https://docs.docker.com/get-docker/"
    docker compose version >/dev/null 2>&1 || fail "需要 Docker Compose V2"

    if [[ "${1:-}" != "--docker" ]]; then
        command -v python3 >/dev/null 2>&1 || fail "需要 Python 3.11+, 请安装"
        command -v node >/dev/null 2>&1 || fail "需要 Node.js 20+, 请安装"

        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
        [[ "$(echo "$PY_VER >= 3.11" | bc -l 2>/dev/null || echo 1)" == "1" ]] || true
        [[ "$NODE_VER" -ge 18 ]] || warn "Node.js 版本 $NODE_VER, 建议 20+"
    fi

    ok "前置依赖检查通过"
}

# ── 初始化环境变量 ──
init_env_files() {
    info "初始化环境变量文件..."

    if [[ ! -f "$SERVER_DIR/.env" ]]; then
        cp "$SERVER_DIR/.env.example" "$SERVER_DIR/.env"
        warn "已创建 server/.env (从 .env.example 复制), 请填写 LLM API Key"
    else
        ok "server/.env 已存在"
    fi

    if [[ ! -f "$WEB_DIR/.env" ]]; then
        cp "$WEB_DIR/.env.example" "$WEB_DIR/.env"
        ok "已创建 web/.env"
    else
        ok "web/.env 已存在"
    fi
}

# ── 启动基础设施 ──
start_infra() {
    info "启动基础设施 (PostgreSQL + Redis + MinIO)..."
    docker compose -f "$COMPOSE_FILE" up -d postgres redis minio

    info "等待 PostgreSQL 就绪..."
    local retries=30
    while ! docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U pdfsku >/dev/null 2>&1; do
        retries=$((retries - 1))
        [[ $retries -le 0 ]] && fail "PostgreSQL 启动超时"
        sleep 2
    done
    ok "PostgreSQL 就绪"

    info "等待 Redis 就绪..."
    retries=20
    while ! docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping >/dev/null 2>&1; do
        retries=$((retries - 1))
        [[ $retries -le 0 ]] && fail "Redis 启动超时"
        sleep 2
    done
    ok "Redis 就绪"

    info "等待 MinIO 就绪..."
    retries=20
    while ! docker compose -f "$COMPOSE_FILE" exec -T minio mc ready local >/dev/null 2>&1; do
        retries=$((retries - 1))
        [[ $retries -le 0 ]] && warn "MinIO 可能未就绪, 继续..."
        sleep 2
    done
    ok "MinIO 就绪"
}

# ── 后端初始化 ──
setup_backend() {
    info "配置后端 Python 环境..."
    cd "$SERVER_DIR"

    if [[ ! -f "$VENV/bin/python" ]]; then
        fail "虚拟环境不存在: $VENV，请先创建: python3 -m venv $VENV"
    fi
    ok "使用虚拟环境: $VENV"

    info "安装 Python 依赖..."
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r requirements.txt
    ok "Python 依赖安装完成"

    # 布局检测依赖 (可选, 用于合成大图拆分)
    if "$VENV/bin/pip" show doclayout-yolo >/dev/null 2>&1; then
        ok "布局检测依赖已安装 (跳过)"
    else
        info "安装布局检测依赖 (doclayout-yolo + ultralytics, 首次安装较慢)..."
        "$VENV/bin/pip" install doclayout-yolo ultralytics \
            && ok "布局检测依赖安装完成" \
            || warn "布局检测依赖安装失败 (可选功能, 不影响核心流程)"
    fi

    # 下载 DocLayout-YOLO 模型 (可选)
    if [[ ! -f "models/doclayout_yolo.pt" ]]; then
        info "下载 DocLayout-YOLO 模型 (~40MB)..."
        mkdir -p models
        wget -q --show-progress -O models/doclayout_yolo.pt \
            "https://huggingface.co/juliozhao/DocLayout-YOLO-DocStructBench/resolve/main/doclayout_yolo_docstructbench_imgsz1024.pt" 2>/dev/null \
            && ok "DocLayout-YOLO 模型下载完成" \
            || warn "模型下载失败 (可选功能, 合成大图页面将跳过布局检测)"
    else
        ok "DocLayout-YOLO 模型已存在"
    fi

    info "运行数据库迁移..."
    PYTHONPATH="$SERVER_DIR/src" "$VENV/bin/python" -m alembic upgrade head 2>/dev/null \
        && ok "数据库迁移完成" \
        || warn "数据库迁移失败, 可能需要手动处理"

    # 确保上传目录存在
    mkdir -p data/tus-uploads
}

# ── 前端初始化 ──
setup_frontend() {
    info "配置前端 Node.js 环境..."
    cd "$WEB_DIR"

    info "安装前端依赖..."
    npm install --silent 2>/dev/null
    ok "前端依赖安装完成"
}

# ── 启动开发服务 ──
start_dev_services() {
    info "启动后端服务..."
    cd "$SERVER_DIR"
    PYTHONPATH="$SERVER_DIR/src" "$VENV/bin/python" -m uvicorn "pdf_sku.main:create_app" --factory \
        --host 0.0.0.0 --port 8000 --reload --reload-dir src &
    local SERVER_PID=$!

    info "启动前端开发服务器..."
    cd "$WEB_DIR"
    npm run dev &
    local WEB_PID=$!

    # 等待后端就绪
    info "等待后端就绪..."
    local retries=30
    while ! curl -sf http://localhost:8000/api/v1/health >/dev/null 2>&1; do
        retries=$((retries - 1))
        [[ $retries -le 0 ]] && { warn "后端启动超时, 请检查日志"; break; }
        sleep 2
    done
    [[ $retries -gt 0 ]] && ok "后端已就绪"

    echo ""
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  PDF-SKU 开发环境已启动${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo "  后端 API:  http://localhost:8000"
    echo "  API 文档:  http://localhost:8000/docs"
    echo "  前端:      http://localhost:5173"
    echo ""
    echo "  PostgreSQL: localhost:5432  (pdfsku/pdfsku)"
    echo "  Redis:      localhost:6379"
    echo "  MinIO:      localhost:9000  (console: 9001)"
    echo "              minioadmin / minioadmin"
    echo ""
    echo -e "  按 ${YELLOW}Ctrl+C${NC} 停止前后端服务"
    echo -e "  基础设施需单独停止: ${CYAN}./setup.sh --stop${NC}"
    echo ""

    trap "kill $SERVER_PID $WEB_PID 2>/dev/null; echo ''; ok '前后端已停止 (基础设施仍在运行)'" EXIT INT TERM
    wait
}

# ── Docker 全栈部署 ──
docker_deploy() {
    info "Docker 全栈构建并启动..."
    docker compose -f "$COMPOSE_FILE" up -d --build

    echo ""
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo -e "${GREEN}  PDF-SKU Docker 全栈已启动${NC}"
    echo -e "${GREEN}════════════════════════════════════════${NC}"
    echo ""
    echo "  前端:      http://localhost"
    echo "  后端 API:  http://localhost:8000"
    echo "  MinIO:     http://localhost:9001"
    echo ""
    echo "  查看日志:  docker compose -f $COMPOSE_FILE logs -f"
    echo "  停止:      ./setup.sh --stop"
    echo ""
}

# ── 停止所有服务 ──
stop_all() {
    info "停止所有 Docker 服务..."
    docker compose -f "$COMPOSE_FILE" down
    ok "所有服务已停止"
}

# ── 清除数据重建 ──
reset_all() {
    warn "即将清除所有数据 (数据库、Redis、MinIO) 并重建!"
    read -rp "确认? (输入 yes): " confirm
    [[ "$confirm" == "yes" ]] || { info "已取消"; exit 0; }

    info "停止并清除容器和数据卷..."
    docker compose -f "$COMPOSE_FILE" down -v
    ok "数据已清除"

    info "重新启动..."
    start_infra
    setup_backend
    ok "环境已重建"
}

# ── 主入口 ──
main() {
    cd "$ROOT_DIR"
    case "${1:-}" in
        --infra)
            check_prerequisites --docker
            init_env_files
            start_infra
            echo ""
            ok "基础设施已启动, 可运行后端:"
            echo "  cd server && PYTHONPATH=src ~/envs/pdf/bin/python -m uvicorn pdf_sku.main:create_app --factory --reload --port 8000"
            ;;
        --docker)
            check_prerequisites --docker
            init_env_files
            docker_deploy
            ;;
        --stop)
            stop_all
            ;;
        --reset)
            reset_all
            ;;
        --help|-h)
            echo "用法: ./setup.sh [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)     完整搭建: 基础设施 + 后端 + 前端, 启动开发模式"
            echo "  --infra      只启动基础设施 (PostgreSQL/Redis/MinIO)"
            echo "  --docker     Docker 全栈部署 (构建镜像并启动所有服务)"
            echo "  --stop       停止所有 Docker 服务"
            echo "  --reset      清除所有数据并重建 (慎用)"
            echo "  --help       显示此帮助"
            ;;
        *)
            check_prerequisites
            init_env_files
            start_infra
            setup_backend
            setup_frontend
            start_dev_services
            ;;
    esac
}

main "$@"
