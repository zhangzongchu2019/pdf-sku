# 跨模块变更附录 — V1.1 增量

> **关联文档**: Evaluator V1.1 / Output V1.1 / Collaboration V1.1 / Feedback V1.1 / Config V1.1  
> **本文归集**: 5 项跨模块修改（DB Migration + Schema + 异常分类链）

---

## 1. DB Migration（P1-X1 ~ P1-X4）

### 1.1 P1-X1: INV-03 DB 约束（搜索可用图片最小边 ≥ 640px）

**来源**: Qwen3 — BA §4.4a INV-03 未落地到数据库层  
**影响模块**: Output, Pipeline

```sql
-- Migration: 20250215_001_inv03_search_eligible_check.sql
ALTER TABLE sku_images
    ADD CONSTRAINT chk_inv03_search_eligible
    CHECK (search_eligible = false OR short_edge >= 640);

COMMENT ON CONSTRAINT chk_inv03_search_eligible ON sku_images IS
    'INV-03: 搜索可用图片最小边 ≥ 640px（BA §4.4a）';
```

**回滚**:
```sql
ALTER TABLE sku_images DROP CONSTRAINT chk_inv03_search_eligible;
```

---

### 1.2 P1-X2: SKU 补 SUPERSEDED 状态 + Image 补 status 字段

**来源**: Qwen3 — 跨页属性继承修正后旧 SKU 需标记为已废弃  
**影响模块**: Output, Collaboration

```sql
-- Migration: 20250215_002_sku_superseded_image_status.sql

-- 1) SKU 状态枚举新增 SUPERSEDED
ALTER TYPE sku_status ADD VALUE IF NOT EXISTS 'SUPERSEDED'
    AFTER 'MERGED';

COMMENT ON TYPE sku_status IS
    'V1.1: 新增 SUPERSEDED — 跨页合并/属性修正后被取代的旧版 SKU';

-- 2) sku_images 表补 status 字段
ALTER TABLE sku_images
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'REPLACED', 'DELETED'));

CREATE INDEX idx_sku_images_status ON sku_images(status) WHERE status != 'ACTIVE';
```

**关联代码变更**:
- `output/json_generator.py`: 组装时跳过 `status != 'ACTIVE'` 的图片
- `output/incremental_importer.py`: upsert 时将旧 SKU 标记为 SUPERSEDED

---

### 1.3 P1-X3: pages 表补 parser_backend / skus 表补 attribute_source

**来源**: Qwen3 — Evaluator/Feedback 闭环需追溯解析来源  
**影响模块**: Pipeline, Evaluator, Feedback

```sql
-- Migration: 20250215_003_parser_attribute_source.sql

-- 1) pages 表补 parser_backend
ALTER TABLE pages
    ADD COLUMN IF NOT EXISTS parser_backend VARCHAR(30);

COMMENT ON COLUMN pages.parser_backend IS
    '解析后端：GEMINI_PRO / QWEN_STANDARD / HUMAN_MANUAL（闭环追溯用）';

-- 2) skus 表补 attribute_source
ALTER TABLE skus
    ADD COLUMN IF NOT EXISTS attribute_source VARCHAR(30) DEFAULT 'AI_EXTRACTED'
    CHECK (attribute_source IN (
        'AI_EXTRACTED',       -- AI 直接提取
        'HUMAN_CORRECTED',    -- 人工修正
        'CROSS_PAGE_MERGED',  -- 跨页合并
        'PROMOTED'            -- 属性升级（非标→标准）
    ));

CREATE INDEX idx_skus_attribute_source ON skus(attribute_source);
```

**关联代码变更**:
- `pipeline/page_processor.py`: 写入 `pages.parser_backend`
- `collaboration/annotation_handler.py`: 人工修正时更新 `skus.attribute_source = 'HUMAN_CORRECTED'`
- `feedback/calibration_engine.py`: 偏差分析可按 `attribute_source` 分层统计

---

### 1.4 P1-X4: sku_image_bindings 增加 revision 字段

**来源**: Kimi — 人工修正绑定关系后 Output 应读最新版本  
**影响模块**: Output, Collaboration

```sql
-- Migration: 20250215_004_binding_revision.sql

ALTER TABLE sku_image_bindings
    ADD COLUMN IF NOT EXISTS revision INTEGER DEFAULT 1;

-- 唯一约束：同一绑定的最新版本
CREATE UNIQUE INDEX idx_binding_latest
    ON sku_image_bindings(sku_id, image_id)
    WHERE is_latest = true;

ALTER TABLE sku_image_bindings
    ADD COLUMN IF NOT EXISTS is_latest BOOLEAN DEFAULT true;

COMMENT ON COLUMN sku_image_bindings.revision IS
    'V1.1: 绑定版本号，人工修正时 revision++，Output 读 is_latest=true 的记录';
```

**关联代码变更**:
- `collaboration/annotation_handler.py`: 绑定修正时创建新 revision、旧版 `is_latest=false`
- `output/json_generator.py`: 组装时 `WHERE is_latest = true`
- `output/import_adapter.py`: 幂等键包含 revision（P1-O4 已实现）

---

## 2. 异常传播链分类（P1-X5）

**来源**: Kimi — Pipeline 各阶段异常需统一分类，决定重试 vs 降级 vs 告警

### 2.1 异常层次结构

```python
# app/common/exceptions.py

class PDFSKUBaseError(Exception):
    """所有业务异常基类"""
    def __init__(self, message: str, code: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable

# === 可重试异常（Pipeline 自动重试） ===
class RetryableError(PDFSKUBaseError):
    def __init__(self, message, code, max_retries=3):
        super().__init__(message, code, retryable=True)
        self.max_retries = max_retries

class LLMTimeoutError(RetryableError):
    """LLM API 超时 → 重试 3 次后降级 HUMAN_ALL"""
    def __init__(self, message="LLM timeout"):
        super().__init__(message, "LLM_TIMEOUT", max_retries=3)

class LLMRateLimitError(RetryableError):
    """LLM 限流 → 退避重试"""
    def __init__(self, message="LLM rate limited", retry_after=30):
        super().__init__(message, "LLM_RATE_LIMIT", max_retries=5)
        self.retry_after = retry_after

class StorageError(RetryableError):
    """存储暂时不可用（Redis/DB 连接中断）"""
    def __init__(self, message="Storage unavailable"):
        super().__init__(message, "STORAGE_ERROR", max_retries=3)

class ImportServerError(RetryableError):
    """下游系统 5xx"""
    def __init__(self, message="Import server error"):
        super().__init__(message, "IMPORT_5XX", max_retries=3)

# === 不可重试异常（降级处理） ===
class DegradeError(PDFSKUBaseError):
    """需要降级的异常 → 路由改为 HUMAN_ALL/HUMAN_PAGE"""
    def __init__(self, message, code, degrade_route="HUMAN_ALL"):
        super().__init__(message, code, retryable=False)
        self.degrade_route = degrade_route

class LLMCircuitOpenError(DegradeError):
    """LLM 熔断器打开 → 整个 Job 降级"""
    def __init__(self):
        super().__init__("LLM circuit open", "LLM_CIRCUIT_OPEN")

class EvalFailedError(DegradeError):
    """[V1.1 P0-3] 评估失败 → 降级"""
    def __init__(self, message="Evaluation failed"):
        super().__init__(message, "EVAL_FAILED")

# === 业务异常（不重试、不降级，直接报错） ===
class BusinessError(PDFSKUBaseError):
    """业务规则违反"""
    def __init__(self, message, code):
        super().__init__(message, code, retryable=False)

class ImportDataError(BusinessError):
    """下游 4xx 数据错误 → 不重试"""
    pass

class ConfigNotFoundError(BusinessError):
    """[V1.1 P1-FC6] 冻结版本不存在"""
    pass

class ImportConflictError(BusinessError):
    """乐观锁冲突"""
    pass
```

### 2.2 Pipeline Orchestrator 异常处理矩阵

```python
# app/pipeline/error_handler.py

EXCEPTION_POLICY = {
    # 可重试
    LLMTimeoutError:     {"action": "retry",   "max": 3, "then": "degrade"},
    LLMRateLimitError:   {"action": "retry",   "max": 5, "then": "degrade", "backoff": "retry_after"},
    StorageError:        {"action": "retry",   "max": 3, "then": "fail_job"},
    ImportServerError:   {"action": "retry",   "max": 3, "then": "mark_failed"},
    # 降级
    LLMCircuitOpenError: {"action": "degrade", "route": "HUMAN_ALL"},
    EvalFailedError:     {"action": "degrade", "route": "HUMAN_ALL"},
    # 业务错误
    ImportDataError:     {"action": "mark_failed", "retryable": False},
    ConfigNotFoundError: {"action": "suspend_job"},
    BusinessError:       {"action": "log_and_skip"},
}

async def handle_page_error(job_id: str, page_no: int, error: Exception):
    """统一异常处理入口"""
    policy = EXCEPTION_POLICY.get(type(error))
    if not policy:
        logger.error("unhandled_exception", job=job_id, page=page_no,
            error_type=type(error).__name__, error=str(error))
        metrics.pipeline_unhandled_error_total.inc()
        return

    match policy["action"]:
        case "retry":
            # 由上层 retry_with_backoff 处理
            raise
        case "degrade":
            await degrade_page(job_id, page_no, policy["route"], str(error))
        case "mark_failed":
            await mark_page_failed(job_id, page_no, str(error))
        case "suspend_job":
            await suspend_job(job_id, str(error))
        case "log_and_skip":
            logger.warning("business_error_skipped",
                job=job_id, page=page_no, error=str(error))
```

### 2.3 异常传播链示意

```
LLM Adapter 抛出 LLMTimeoutError(retryable=True)
    ↓
Pipeline PageProcessor 捕获 → retry 3 次
    ↓ 重试耗尽
Pipeline 将 RetryableError 包装为 EvalFailedError(degrade_route=HUMAN_ALL)
    ↓
Evaluator 捕获 → 创建降级 Evaluation → route=HUMAN_ALL
    ↓
FallbackMonitor 记录连续失败计数 → 达到阈值 → 挂起 Job
```

---

## 3. 修改汇总

| # | 类型 | 影响表/文件 | 优先级 |
|---|------|------------|--------|
| P1-X1 | DB Migration | sku_images CHECK 约束 | P1 |
| P1-X2 | DB Migration | sku_status 枚举 + sku_images.status | P1 |
| P1-X3 | DB Migration | pages.parser_backend + skus.attribute_source | P1 |
| P1-X4 | DB Migration | sku_image_bindings.revision + is_latest | P1 |
| P1-X5 | Code Schema | common/exceptions.py + pipeline/error_handler.py | P1 |
| **P1-X6** | **DB Migration + Code** | **users 表 + auth/ 模块（JWT/RBAC）** | **P1** |

**P1-X6 Auth 模块跨模块影响**：

| 影响模块 | 变更内容 |
|---------|---------|
| **Gateway** | `create_job` 增加 `Depends(UploaderUser)` 守卫，`uploaded_by` 从 `user.username` 获取，`merchant_id` 从 `user.merchant_id` 推导 |
| **Collaboration** | 所有 task 操作端点增加 `Depends(AnnotatorUser)` 守卫，`operator` 从 `user.username` 获取 |
| **DDL** | 新增 `users` 表（18 张表），Migration 002_add_users.py |
| **Settings** | 新增 `JWT_SECRET_KEY` 环境变量，`JWT_EXPIRE_HOURS` 可选（默认 24） |
| **依赖** | 新增 python-jose[cryptography] 包 |

**执行顺序**: X1 → X3 → X2 → X4（无循环依赖），X5/X6 可并行开发。
