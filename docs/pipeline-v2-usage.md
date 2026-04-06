---
name: Pipeline V2 使用说明
description: 本地切换到 pipeline_v2、运行服务、跑 benchmark 与查看结果的方法
type: project
---

# Pipeline V2 使用说明

这份文档只回答一件事：

- 怎么把系统切到 `pipeline_v2`
- 怎么运行看效果
- 去哪里看结果

不讲设计原理。设计请看：

- [pipeline-design.md](/home/fulei/codes/pdf-sku/docs/pipeline-design.md)
- [pipeline-implementation.md](/home/fulei/codes/pdf-sku/docs/pipeline-implementation.md)
- [pipeline-export-contract.md](/home/fulei/codes/pdf-sku/docs/pipeline-export-contract.md)

## 1. 两种运行方式

推荐分成两种：

1. 在线 Job 模式
   - 适合拿单个真实 PDF 走完整上传链路
   - 需要 PostgreSQL、Redis、MinIO
   - 结果会落到 job 目录和数据库里

2. 离线 Benchmark 模式
   - 适合批量对比 `legacy` 和 `v2`
   - 不依赖数据库、Redis、MinIO
   - 结果会写到本地 `data/benchmark_cache`

如果你现在只是想“先看效果”，优先建议：

- 单文件体验：在线 Job 模式
- 批量对比：离线 Benchmark 模式

## 2. 核心开关

`pipeline_v2` 相关环境变量：

- `PIPELINE_IMPLEMENTATION=v2`
  - 切换到底层新 pipeline
- `PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false`
  - 建议默认关闭，避免结果偷偷回退到旧 pipeline
- `PIPELINE_V2_REGION_REFINE_ENABLED=true`
  - 是否启用区域级 VLM refine
- `PIPELINE_V2_PAGE_VERIFY_ENABLED=true`
  - 是否启用页面级 verify

推荐默认配置：

```bash
PIPELINE_IMPLEMENTATION=v2
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false
PIPELINE_V2_REGION_REFINE_ENABLED=true
PIPELINE_V2_PAGE_VERIFY_ENABLED=true
```

如果你想先做更保守的排查，可以先关掉 VLM 后处理：

```bash
PIPELINE_V2_REGION_REFINE_ENABLED=false
PIPELINE_V2_PAGE_VERIFY_ENABLED=false
```

## 3. 在线 Job 模式

### 3.1 前置条件

在 [server/README.md](/home/fulei/codes/pdf-sku/server/README.md) 的基础上，至少要有：

1. 安装依赖
2. 启动 PostgreSQL / Redis / MinIO
3. 执行数据库迁移

推荐命令：

```bash
cd /home/fulei/codes/pdf-sku/server
./.venv/bin/pip install -e ".[dev]"
./.venv/bin/alembic upgrade head
```

如果基础设施使用配套仓库：

```bash
cd /home/fulei/codes/pdf-sku-infra
docker compose up -d
```

### 3.2 启动服务

在 `server/` 目录下启动：

```bash
cd /home/fulei/codes/pdf-sku/server
PIPELINE_IMPLEMENTATION=v2 PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false PIPELINE_V2_REGION_REFINE_ENABLED=true   PIPELINE_V2_PAGE_VERIFY_ENABLED=true ./.venv/bin/python -m uvicorn pdf_sku.main:create_app --factory --reload --port 8000
```

### 3.3 检查服务是否正常

打开：

- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- Swagger：`http://127.0.0.1:8000/docs`

如果健康检查返回 `healthy`，说明在线链路依赖基本正常。

### 3.4 怎么上传 PDF

最简单的方式不是手写 TUS 请求，而是：

- 继续使用你现在已有的前端上传流程
- 或者在已有调用脚本里照常调用 `/api/v1/uploads` + `/api/v1/jobs`

因为这次切换只影响底层 `PageProcessor`，不改上传协议。

也就是说：

- 前端/调用方式不变
- 只要后端环境变量切到 `PIPELINE_IMPLEMENTATION=v2`
- 任务就会走新 pipeline

创建 Job 的核心参数仍然是：

```json
{
  "upload_id": "xxx",
  "merchant_id": "xxx",
  "category": "optional"
}
```

对应接口：

- `POST /api/v1/uploads`
- `PATCH /api/v1/uploads/{id}`
- `POST /api/v1/jobs`

### 3.5 去哪里看结果

在线 Job 模式下，最常看这几处：

- 任务结果 JSON：`GET /api/v1/jobs/{job_id}/result`
- 任务图片静态目录：`/images/jobs/...`
- 若你有现成前端，继续在前端结果页看

本地默认 job 目录来自：

- `JOB_DATA_DIR`
- 默认值是 `/data/jobs`

也就是说，单个任务结果通常会落在类似路径：

```text
/data/jobs/<job_id>/result.json
```

## 4. 离线 Benchmark 模式

这条链路最适合“批量看效果”和“对比 legacy / v2”。

优点：

- 不依赖 PostgreSQL / Redis / MinIO
- 不需要上传
- 可以直接批量跑参考数据集

### 4.1 数据目录

默认参考数据根目录来自：

- `PDF_DATA_ROOT`
- 默认值见 [excel_parser.py](/home/fulei/codes/pdf-sku/server/src/pdf_sku/benchmark/excel_parser.py)

默认会指向项目同级的 `pdf整理` 目录。

如果你的数据不在默认目录，可以显式指定：

```bash
--data-root /your/data/root
```

### 4.2 先扫描数据集

```bash
cd /home/fulei/codes/pdf-sku/server
PIPELINE_IMPLEMENTATION=v2 \
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false \
./.venv/bin/python -m pdf_sku.benchmark scan
```

如果只想看某一批：

```bash
./.venv/bin/python -m pdf_sku.benchmark scan --filter '七里森*'
```

### 4.3 跑数据集

```bash
cd /home/fulei/codes/pdf-sku/server
PIPELINE_IMPLEMENTATION=v2 \
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false \
PIPELINE_V2_REGION_REFINE_ENABLED=true \
PIPELINE_V2_PAGE_VERIFY_ENABLED=true \
./.venv/bin/python -m pdf_sku.benchmark run --filter '七里森*' --force --tag v2
```

说明：

- `--filter`
  - 只跑匹配的数据集
- `--force`
  - 强制重跑，自动归档旧缓存
- `--tag`
  - 给这轮结果打标签

### 4.4 对比结果

```bash
cd /home/fulei/codes/pdf-sku/server
./.venv/bin/python -m pdf_sku.benchmark compare --filter '七里森*'
```

如果你想一把跑完：

```bash
cd /home/fulei/codes/pdf-sku/server
PIPELINE_IMPLEMENTATION=v2 \
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false \
./.venv/bin/python -m pdf_sku.benchmark full --filter '七里森*' --force --tag v2
```

### 4.5 导出 Excel

```bash
cd /home/fulei/codes/pdf-sku/server
./.venv/bin/python -m pdf_sku.benchmark export --filter '七里森*' --output data/benchmark_exports
```

### 4.6 去哪里看结果

benchmark 主要产出在：

- 缓存 JSON：`server/data/benchmark_cache`
- 历史归档：`server/data/benchmark_history`
- 导出 Excel：`server/data/benchmark_exports`
- 报告：`server/data/benchmark_reports/report.md`

如果你已经启动了后端服务，还可以直接打开：

- `http://127.0.0.1:8000/benchmark/viewer`

它会读取 `benchmark_cache` 下的 JSON 做可视化。

## 5. 最小单文件脚本方式

如果你不想走上传链路，也不想准备 benchmark 数据集，可以直接用一个最小脚本跑单个 PDF。

在 `server/` 目录下执行：

```bash
PIPELINE_IMPLEMENTATION=v2 \
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false \
./.venv/bin/python - <<'PY'
import asyncio
import json
from concurrent.futures import ProcessPoolExecutor
import fitz

from pdf_sku.main import create_llm_service
from pdf_sku.pipeline.catalog_profiler import scan_catalog
from pdf_sku.pipeline_factory import build_page_processor
from pdf_sku.config.service import ConfigProvider

PDF_PATH = "/absolute/path/to/your.pdf"

async def main():
    llm = create_llm_service(redis=None)
    pool = ProcessPoolExecutor(max_workers=2)
    processor = build_page_processor(
        llm_service=llm,
        process_pool=pool,
        config_provider=ConfigProvider(),
        pipeline_implementation="v2",
    )
    catalog_profile = scan_catalog(PDF_PATH)
    doc = fitz.open(PDF_PATH)
    total_pages = doc.page_count
    doc.close()

    pages = []
    for page_no in range(1, total_pages + 1):
        result = await processor.process_page(
            job_id="local-v2-demo",
            file_path=PDF_PATH,
            page_no=page_no,
            catalog_profile=catalog_profile,
        )
        pages.append({
            "page_no": page_no,
            "status": result.status,
            "page_type": result.page_type,
            "sku_count": len(result.skus),
            "skus": [
                {
                    "sku_id": sku.sku_id,
                    "attributes": sku.attributes,
                    "confidence": sku.confidence,
                    "extraction_method": sku.extraction_method,
                }
                for sku in result.skus
            ],
        })

    processor.clear_job_cache("local-v2-demo")
    pool.shutdown(wait=False)
    print(json.dumps(pages, ensure_ascii=False, indent=2))

asyncio.run(main())
PY
```

这条方式适合：

- 先快速看某个 PDF 的原始抽取结果
- 不走数据库
- 不走上传
- 不做 benchmark 对比

## 6. 推荐的排查顺序

如果你第一次跑 `pipeline_v2`，建议按这个顺序来：

1. 先跑单文件脚本
   - 先确认 `v2` 能处理这个 PDF
2. 再跑在线 Job 模式
   - 确认上传链路和结果落盘正常
3. 最后跑 benchmark
   - 看批量效果和对比指标

## 7. 常见开关建议

### 7.1 想看最纯的 v2 效果

```bash
PIPELINE_IMPLEMENTATION=v2
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false
PIPELINE_V2_REGION_REFINE_ENABLED=true
PIPELINE_V2_PAGE_VERIFY_ENABLED=true
```

### 7.2 想先排查启发式链路，不引入 VLM refine / verify

```bash
PIPELINE_IMPLEMENTATION=v2
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=false
PIPELINE_V2_REGION_REFINE_ENABLED=false
PIPELINE_V2_PAGE_VERIFY_ENABLED=false
```

### 7.3 想先保守上线

```bash
PIPELINE_IMPLEMENTATION=v2
PIPELINE_V2_ALLOW_LEGACY_FALLBACK=true
```

这时新 pipeline 处理失败时，才允许回退到 legacy。

## 8. 当前已知边界

当前 `pipeline_v2` 适合重点观察这些能力：

- 长表格首页表头继承
- 普通页区域提议
- OCR / layout 证据接入
- `visual_only` 商品单元
- 页面级 `region_refine` / `page_verify`

当前还不适合期待：

- 完整的字段级证据对象导出
- 完整有限重入控制
- 所有复杂跨页语义重构

## 9. 一句话建议

如果你现在只是想“快点看效果”，最短路径是：

1. 在 `server/` 目录下用环境变量切到 `PIPELINE_IMPLEMENTATION=v2`
2. 先跑单文件脚本或 benchmark `run`
3. 再决定要不要走完整上传链路
