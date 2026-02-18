# PDF-SKU 系统模块间接口契约总表

> **版本**: V1.2（对齐 OpenAPI V2.0 + 前端详设 V1.1）  
> **来源**: TA V1.6 §2.4 Protocol 定义 + 各模块详设 V1.1/V1.2 + OpenAPI V2.0  
> **原则**: 模块间仅通过 Protocol 接口交互，不直接依赖实现类

---

## V1.2 变更记录

| 变更 | 来源 |
|------|------|
| §2.4 TaskManager +auto_pick_next() | OpenAPI V2.0 POST /tasks/next |
| §2.4 TaskManager +batch_skip() | OpenAPI V2.0 POST /ops/tasks/batch-skip |
| §2.8 FeedbackCollector +submit_upgrade_suggestion() | OpenAPI V2.0 /ops/custom-attr-upgrades |
| §2.11 新增 AnnotationService（独立标注端点）| OpenAPI V2.0 POST /annotations |
| §3 SSE 事件 7→9（+heartbeat, +pages_batch_update）| OpenAPI V2.0 SSE schema |
| §5 新增 INV-10~INV-12 不变式 | OpenAPI V2.0 双轨状态/task_next 原子性 |
| §2.2 Evaluation DTO +route_reason/thresholds_used | OpenAPI V2.0 Evaluation 增强 |
| §2.5 ImportResult DTO +import_confirmation | OpenAPI V2.0 SKU.import_confirmation |
| §2.12 新增 Auth 模块（JWT/RBAC）依赖注入契约 | Auth 模块 V1.2 |

---

## 1. 模块依赖矩阵

```
调用方 ↓ \ 被调方 →   Gateway  Evaluator  Pipeline  Collab  Output  Config  LLM    Feedback  Parser  Storage  Auth
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Gateway                  —        ✅         —        —       —       ✅      —       —        —       ✅      ✅
Evaluator                —         —         —        —       —       ✅      ✅      —        ✅      —       —
Pipeline                 —         —         —        ✅      ✅      ✅      ✅      —        ✅      ✅      —
Collaboration            —         —        ✅(retry)  —      ✅       —       —       ✅       —       —      ✅
Output                   —         —         —        —       —       ✅      —       ✅       —       ✅      —
Feedback                 —         —         —        —       —       ✅      —        —       —       —       —
Auth                     —         —         —        —       —       —       —        —       —       —       —
```

**依赖链**: Gateway → Evaluator → Pipeline → Collaboration → Output → Feedback，Config 横切所有模块，Auth 横切 Gateway + Collaboration（通过 FastAPI Depends 注入）

---

## 2. Protocol 接口签名汇总

### 2.1 JobCreator（Gateway 模块）

```python
@runtime_checkable
class JobCreator(Protocol):
    async def create_job(
        self, file_path: str, merchant_id: str, category: str | None
    ) -> PDFJob: ...

    async def requeue_job(
        self, job_id: str, new_worker_id: str
    ) -> PDFJob: ...

    # [V1.2] user_status 自动同步
    def compute_user_status(self, internal_status: str) -> str: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `create_job` | API Handler | POST /api/v1/jobs | PDFJob(status=UPLOADED, user_status='processing') | ValidationError → 400 |
| `requeue_job` | OrphanScanner | 心跳超时检测 | PDFJob(status=PROCESSING) | JobNotFoundError → 404 |
| `compute_user_status` | 所有状态变更点 | status 每次变更时 | user_status 字符串 | — |

**[V1.2] user_status 映射规则**（在 Gateway 层统一实现）：
```python
USER_STATUS_MAP = {
    'UPLOADED': 'processing', 'EVALUATING': 'processing',
    'EVALUATED': 'processing', 'PROCESSING': 'processing',
    'PARTIAL_IMPORTED': 'partial_success', 'PARTIAL_FAILED': 'partial_success',
    'FULL_IMPORTED': 'completed',
    'DEGRADED_HUMAN': 'needs_manual',
    'EVAL_FAILED': 'failed', 'REJECTED': 'failed',
    'CANCELLED': 'failed', 'ORPHANED': 'failed',
}
```

### 2.2 DocumentEvaluator（Evaluator 模块）

```python
@runtime_checkable
class DocumentEvaluator(Protocol):
    async def evaluate(
        self, job: PDFJob, prescan: PrescanResult
    ) -> Evaluation: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `evaluate` | Pipeline Orchestrator | Job 进入 EVALUATING | Evaluation(route=AUTO/HYBRID/HUMAN_ALL) | EvalFailedError → 降级 HUMAN_ALL |

**输入 DTO**:
```python
class PrescanResult(BaseModel):
    total_pages: int
    blank_pages: list[int]
    encrypted: bool
    has_js: bool
    page_features: dict[int, dict] | None
    # [V1.2] raw_metrics 子对象（对齐 OpenAPI V2.0）
    raw_metrics: RawMetrics | None

class RawMetrics(BaseModel):
    total_pages: int
    blank_page_count: int
    blank_rate: float
    ocr_rate: float
    image_count: int
```

**输出 DTO**:
```python
class Evaluation(BaseModel):
    file_hash: str
    config_version: str
    doc_confidence: float          # 0.0~1.0
    route: str                     # AUTO | HYBRID | HUMAN_ALL
    route_reason: str | None       # [V1.2] 路由决策原因
    degrade_reason: str | None
    dimension_scores: dict
    prescan: PrescanResult
    sampling: SamplingInfo
    page_evaluations: dict[str, float]
    model_used: str
    prompt_version: str | None     # [V1.2]
    thresholds_used: dict | None   # [V1.2] 使用的阈值快照
    evaluated_at: str | None       # [V1.2]
```

### 2.3 PageProcessor（Pipeline 模块）

```python
@runtime_checkable
class PageProcessor(Protocol):
    async def process_page(
        self, job: PDFJob, page_no: int, attempt_no: int
    ) -> PageResult: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `process_page` | Pipeline Orchestrator | 逐页/分片处理 | PageResult | RetryableError → 重试; DegradeError → HUMAN_PAGE |

**核心输出 DTO**:
```python
class PageResult(BaseModel):
    status: str             # COMPLETED | SKIPPED | NEEDS_REVIEW | FAILED
    page_type: str          # A | B | C | D
    needs_review: bool
    skus: list[SKUResult]
    images: list[ImageResult]
    bindings: list[BindingResult]
    export_results: list[ExportResult]
    validation: ValidationResult

class SKUResult(BaseModel):
    sku_id: str
    attributes: dict
    validity: str           # valid | invalid
    source_bbox: list[float]
    confidence: float

class ImageResult(BaseModel):
    image_id: str
    role: str
    path: str
    short_edge: int
    search_eligible: bool
    image_hash: str | None        # [V1.2] pHash
    is_duplicate: bool             # [V1.2]

class BindingResult(BaseModel):
    sku_id: str
    image_id: str
    method: str                    # spatial_proximity | grid_alignment | id_matching | page_inheritance
    confidence: float
    is_ambiguous: bool
    rank: int
```

### 2.4 TaskManager（Collaboration 模块）

```python
@runtime_checkable
class TaskManager(Protocol):
    async def create_task(
        self, job_id: str, page_number: int,
        task_type: str, context: dict
    ) -> HumanTask: ...

    async def complete_task(
        self, task_id: str, result: dict, operator: str
    ) -> HumanTask: ...

    async def revert_task(
        self, task_id: str, operator: str, reason: str
    ) -> HumanTask: ...

    # [V1.2] 自动领取下一个任务（原子 GET+lock）
    async def auto_pick_next(
        self, operator: str
    ) -> HumanTask | None: ...

    # [V1.2] 批量跳过
    async def batch_skip(
        self, task_ids: list[str], operator: str, reason: str | None
    ) -> BatchResult: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `create_task` | Pipeline | 页面 needs_review=true | HumanTask(status=CREATED) | — |
| `complete_task` | API Handler | POST /tasks/{id}/complete | HumanTask(status=COMPLETED) | LockExpiredError → 409 |
| `revert_task` | API Handler | POST /tasks/{id}/revert | HumanTask(status=CREATED) | BusinessError → 400 |
| `auto_pick_next` | API Handler | POST /tasks/next | HumanTask \| None (204 if empty) | ConcurrencyError → 409 重试 |
| `batch_skip` | API Handler | POST /ops/tasks/batch-skip | BatchResult | 部分失败不阻断 |

**[V1.2] auto_pick_next 原子性实现**：
```sql
-- SKIP LOCKED 原子领取（同一 SQL 事务内完成查询+加锁）
UPDATE human_tasks
SET    status = 'PROCESSING', locked_by = :operator, locked_at = now()
WHERE  task_id = (
    SELECT task_id FROM human_tasks
    WHERE  status = 'CREATED'
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
RETURNING *;
```

**HumanTask.context JSONB 结构**:
```json
{
    "page_type": "C",
    "layout_type": "L2",
    "screenshot_url": "/screenshots/page_042.png",
    "ai_result": {"skus": [], "confidence": 0.65},
    "cross_page_table": {"from_page": 41, "to_page": 42},
    "binding_candidates": [{"sku_id": "...", "image_id": "...", "confidence": 0.72}]
}
```

### 2.5 SKUImporter（Output 模块）

```python
@runtime_checkable
class SKUImporter(Protocol):
    async def import_sku(
        self, sku: SKU, job: PDFJob
    ) -> ImportResult: ...

    async def import_page_incremental(
        self, job: PDFJob, page_result: PageResult
    ) -> list[ImportResult]: ...

    # [V1.2] 对账同步（IMPORTED_ASSUMED 异常处理）
    async def sync_job(
        self, job_id: str
    ) -> SyncResult: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `import_sku` | Output IncrementalImporter | 单 SKU 导入 | ImportResult | ImportServerError → 重试3次 |
| `import_page_incremental` | Pipeline `_on_page_done` | 每页完成即触发 | list[ImportResult] | 部分失败不阻断 |
| `sync_job` | API Handler | POST /jobs/{id}/sync | SyncResult | — |

**ImportResult DTO**:
```python
class ImportResult(BaseModel):
    sku_id: str
    success: bool
    downstream_id: str | None
    error_code: str | None
    retryable: bool
    import_confirmation: str       # [V1.2] confirmed | assumed | failed | pending
```

### 2.6 ConfigProvider（Config 模块）

```python
@runtime_checkable
class ConfigProvider(Protocol):
    def get_profile(self, version: str) -> ThresholdProfile: ...
    def get_active_profile(self, category: str | None) -> ThresholdProfile: ...
    def get_category_schema(self, category: str) -> CategorySchema: ...
    # [V1.2] 影响预估
    def get_impact_preview(
        self, profile_id: str, threshold_a: float, threshold_b: float, threshold_pv: float
    ) -> ImpactPreviewResult: ...
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `get_profile` | 所有模块 | 按 frozen_config_version 读取 | ThresholdProfile | ConfigNotFoundError → suspend_job |
| `get_active_profile` | Gateway (Job创建时冻结) | Job 创建 | ThresholdProfile | 返回 global_default |
| `get_category_schema` | Pipeline ConsistencyValidator | SKU 校验 | CategorySchema | 返回 DEFAULT_SCHEMA |
| `get_impact_preview` | API Handler | GET /config/profiles/{id}/impact-preview | ImpactPreviewResult | — |

### 2.7 LLMService（LLM Adapter 模块）

```python
@runtime_checkable
class LLMService(Protocol):
    async def evaluate_document(self, ctx: LLMCallContext) -> list[Score]: ...
    async def classify_page(self, ctx: LLMCallContext) -> ClassifyResult: ...
    async def classify_text(self, ctx: LLMCallContext) -> list[str]: ...
    async def classify_images(self, ctx: LLMCallContext) -> list[str]: ...
    async def classify_layout(self, ctx: LLMCallContext) -> LayoutResult: ...
    async def extract_sku_attrs(self, ctx: LLMCallContext) -> SKUAttrResult: ...
    async def resolve_binding(self, ctx: LLMCallContext) -> BindingHints: ...
```

（签名与 V1.1 一致，内部行为变更见 LLM Adapter V1.2 详设）

### 2.8 FeedbackCollector（Feedback 模块）

```python
@runtime_checkable
class FeedbackCollector(Protocol):
    async def submit_annotation(self, annotation: Annotation) -> None: ...
    async def check_calibration_trigger(self) -> bool: ...
    # [V1.2] 非标属性升级建议
    async def submit_upgrade_suggestion(
        self, attr_name: str, suggested_type: str, merchant_id: str | None, source_count: int
    ) -> str: ...  # 返回 upgrade_id
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `submit_annotation` | Collaboration (task complete 后) | 标注完成 | None | 写入失败不阻断主流程 |
| `check_calibration_trigger` | 定时任务 (03:00) | 每日校准检查 | bool | — |
| `submit_upgrade_suggestion` | PromotionChecker (每日 02:00) | 非标属性频次超阈值 | upgrade_id | — |

### 2.9 ParserAdapter（Pipeline 内部）

```python
@runtime_checkable
class ParserAdapter(Protocol):
    async def parse_page(self, file_path: str, page_no: int) -> ParsedPageIR: ...
    def get_backend_name(self) -> str: ...
```

### 2.10 StorageProvider（横切）

```python
@runtime_checkable
class StorageProvider(Protocol):
    async def read_file(self, relative_path: str) -> bytes: ...
    async def write_file(self, relative_path: str, data: bytes) -> None: ...
    def get_url(self, relative_path: str) -> str: ...
    async def delete_file(self, relative_path: str) -> None: ...
    async def exists(self, relative_path: str) -> bool: ...
```

### 2.11 [V1.2 新增] AnnotationService（独立标注端点）

```python
@runtime_checkable
class AnnotationService(Protocol):
    async def create_annotation(
        self, job_id: str, page_number: int,
        type: str, payload: dict,
        task_id: str | None, operator: str
    ) -> str: ...  # 返回 annotation_id
```

| 方法 | 调用方 | 触发时机 | 返回 | 错误处理 |
|------|--------|---------|------|---------|
| `create_annotation` | API Handler | POST /annotations | annotation_id (UUID) | ValidationError → 400 |

**8 种标注类型**：PAGE_TYPE_CORRECTION、TEXT_ROLE_CORRECTION、IMAGE_ROLE_CORRECTION、SKU_ATTRIBUTE_CORRECTION、BINDING_CORRECTION、CUSTOM_ATTR_CONFIRM、NEW_TYPE_REPORT、LAYOUT_CORRECTION

### 2.12 [V1.2 新增] Auth（认证/鉴权 模块）

Auth 模块不通过 Protocol 接口暴露，而是通过 FastAPI Depends 依赖注入横切 Gateway 和 Collaboration 路由。

**依赖类型**（`auth/dependencies.py`）：

```python
# 基础：从 JWT Bearer Token 解析当前用户
async def get_current_user(token: str = Depends(HTTPBearer())) -> User: ...

# 角色守卫：注入到路由参数，自动校验角色
UploaderUser = Annotated[User, Depends(require_role("uploader", "admin"))]
AnnotatorUser = Annotated[User, Depends(require_role("annotator", "admin"))]
AdminUser = Annotated[User, Depends(require_role("admin"))]
```

**路由端点（9 个）**：

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/v1/auth/login` | POST | 公开 | 用户名+密码 → JWT access_token |
| `/api/v1/auth/register` | POST | AdminUser | 注册新用户 |
| `/api/v1/auth/me` | GET | 已认证 | 获取当前用户信息 |
| `/api/v1/auth/me` | PATCH | 已认证 | 修改 display_name |
| `/api/v1/auth/change-password` | POST | 已认证 | 修改密码（需 old_password 验证）|
| `/api/v1/auth/users` | GET | AdminUser | 用户列表 |
| `/api/v1/auth/users` | POST | AdminUser | 创建用户 |
| `/api/v1/auth/users/{user_id}` | PATCH | AdminUser | 修改用户信息 |
| `/api/v1/auth/users/{user_id}/status` | PATCH | AdminUser | 启用/禁用用户 |

**安全实现**：
- JWT 签发：`python-jose`，算法 HS256，payload: `{sub: user_id, role, exp}`
- 密码存储：`hashlib.pbkdf2_hmac('sha256', password, salt, 100000)` + 随机 16 字节 salt
- 环境变量：`JWT_SECRET_KEY`（必需），`JWT_EXPIRE_HOURS`（默认 24）

**跨模块影响**：
- Gateway `create_job`：`Depends(UploaderUser)` 自动注入当前用户，`uploaded_by = user.username`
- Collaboration task 操作：`Depends(AnnotatorUser)` 自动注入，`operator = user.username`

---

## 3. 跨模块事件契约

### 3.1 Job 状态流转（谁写谁读）

```
UPLOADED ──[Gateway]──→ EVALUATING ──[Evaluator]──→ EVALUATED ──[Pipeline]──→ PROCESSING
                           │                                                      │
                    [Evaluator]                                              [Pipeline]
                           ↓                                                      ↓
                      EVAL_FAILED                                         PARTIAL_IMPORTED
                      REJECTED                                            FULL_IMPORTED
                      DEGRADED_HUMAN                                      PARTIAL_FAILED

每次 status 变更时同步写入 user_status = USER_STATUS_MAP[status]  [V1.2]
```

| 状态转换 | 写入模块 | 触发条件 | user_status | 读取模块 |
|----------|---------|---------|-----------|---------| 
| UPLOADED → EVALUATING | Gateway | Job 创建后 | processing | Evaluator |
| EVALUATING → EVALUATED | Evaluator | 评估完成 | processing | Pipeline |
| EVALUATING → EVAL_FAILED | Evaluator | 评估异常 | failed | Gateway (SSE) |
| EVALUATING → DEGRADED_HUMAN | Evaluator | 全降级 | needs_manual | Collaboration |
| EVALUATED → PROCESSING | Pipeline | 开始处理 | processing | — |
| PROCESSING → FULL_IMPORTED | Pipeline/Output | 所有页导入完成 | completed | Gateway (SSE) |
| PROCESSING → PARTIAL_IMPORTED | Pipeline/Output | 部分页失败但已完成 | partial_success | Gateway (SSE) |
| * → ORPHANED | Gateway (OrphanScanner) | Worker 心跳丢失 | failed | Gateway (requeue) |
| * → CANCELLED | API | 用户取消 | failed | Pipeline (中止) |

### 3.2 Page 状态流转（谁写谁读）

| 状态转换 | 写入模块 | 读取模块 |
|----------|---------|---------| 
| PENDING → BLANK | Pipeline (prescan) | — (跳过) |
| PENDING → AI_PROCESSING | Pipeline | — |
| AI_PROCESSING → AI_COMPLETED | Pipeline | Output |
| AI_COMPLETED → IMPORTED_CONFIRMED | Output | Gateway (SSE) |
| AI_COMPLETED → IMPORTED_ASSUMED | Output | 对账轮询 |
| AI_COMPLETED → IMPORT_FAILED | Output | 重试/告警 |
| PENDING → HUMAN_QUEUED | Pipeline (HYBRID路由) | Collaboration |
| HUMAN_QUEUED → HUMAN_PROCESSING | Collaboration (领取) | — |
| HUMAN_PROCESSING → HUMAN_COMPLETED | Collaboration (提交) | Output |
| * → DEAD_LETTER | Pipeline (重试耗尽) | 运维告警 |

### 3.3 SSE 事件契约（9 种） [V1.2: +2]

| 事件 | 触发模块 | 消费方 | Payload Schema |
|------|---------|--------|---------------|
| `heartbeat` | Gateway | 前端 SSEManager | `{ ts: number }` |
| `page_completed` | Pipeline/Output | 前端 jobStore, annotationStore | SSEPageCompleted |
| `pages_batch_update` | Pipeline | 前端 jobStore | `{ pages: [{page_no, status}] }` |
| `job_completed` | Pipeline/Output | 前端 jobStore, notificationStore | SSEJobCompleted |
| `job_failed` | Evaluator/Pipeline | 前端 jobStore, notificationStore | SSEJobFailed |
| `human_needed` | Pipeline | 前端 annotationStore, notificationStore | SSEHumanNeeded |
| `sla_escalated` | Collaboration | 前端 annotationStore, notificationStore | SSESlaEscalated |
| `sla_auto_resolve` | Collaboration | 前端 annotationStore | SSESlaEscalated |
| `sla_auto_accepted` | Collaboration | 前端 annotationStore | SSESlaEscalated |

---

## 4. 定时任务契约

| 任务 | 模块 | 频率 | 职责 | 读取表 | 写入表 |
|------|------|------|------|--------|--------|
| OrphanScanner | Gateway | 30s | Worker 心跳检测 + 孤儿重提 | pdf_jobs, **worker_heartbeats** | pdf_jobs, state_transitions |
| ReconciliationPoller | Output | 5min | 对账轮询（IMPORTED_ASSUMED 确认） | pages | pages |
| StalledJobChecker | Output | 10min | 超时 Job 终态判定 | pdf_jobs, pages | pdf_jobs |
| LockExpiryScanner | Collaboration | 15s | 过期锁回收 | human_tasks | human_tasks |
| SLAEscalation | Collaboration | 60s | SLA 升级检查 | human_tasks | human_tasks |
| CalibrationTrigger | Feedback | 每日 03:00 | 偏差分析 + 阈值建议 | annotations | calibration_records |
| PromotionChecker | Feedback | 每日 02:00 | 非标属性升级检测 | annotations | calibration_records, **custom_attr_upgrades** |
| ConfigPollFallback | Config | 60s | PubSub 丢失兜底 | threshold_profiles | — (内存刷新) |
| AdaptivePoll | Pipeline | 自适应 | DB 轮询兜底 | pages | pages |
| ApprovalSLACheck | Feedback | 每日 10:00 | 校准审批超时提醒 | calibration_records | — (通知) |

---

## 5. 不变式清单（跨模块强制约束）

| ID | 不变式 | 强制层 | 责任模块 |
|----|--------|--------|---------|
| INV-01 | B < PV < A（路由阈值递增）| Config 写入时校验 | Config |
| INV-02 | ΣWi = 1.0（置信度权重和为 1）| Config 写入时校验 | Config |
| INV-03 | search_eligible=true ⇒ short_edge≥640 | DB CHECK 约束 | Pipeline/Output |
| INV-04 | Job 终态由 import_status 驱动 | Pipeline `_finalize_job()` | Pipeline |
| INV-05 | page_type ∈ {A,B,C,D} | SchemaValidator | Pipeline |
| INV-06 | SKU validity ∈ {valid, invalid}（无 partial）| ConsistencyValidator | Pipeline |
| INV-07 | superseded=true 的 SKU 不参与导入 | Output WHERE 条件 | Output |
| INV-08 | HUMAN_PROCESSING ⇒ locked_by ≠ null | DB 为唯一权威 | Collaboration |
| INV-09 | binding is_latest 唯一约束 | DB UNIQUE INDEX | Pipeline/Collaboration |
| **INV-10** | **user_status = f(status)，每次 status 变更必须同步** | **应用层 + DB trigger fallback** | **Gateway** |
| **INV-11** | **auto_pick_next 原子性：SELECT+UPDATE 在同一事务 + SKIP LOCKED** | **DB 事务** | **Collaboration** |
| **INV-12** | **import_confirmation ∈ {confirmed, assumed, failed, pending}** | **应用层校验** | **Output** |
