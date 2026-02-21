# PDF-SKU Server 系统架构概览 (V0.2.0)

## 模块拓扑

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer (44 endpoints)              │
│  Gateway(16) │ Config(6) │ Collaboration(14) │ Feedback(10) │
└──────┬────────────┬──────────────┬─────────────────┬────────┘
       │            │              │                 │
┌──────▼────────────▼──────────────▼─────────────────▼────────┐
│                    Event Bus (8 event types)                  │
│  JobCreated → EvaluationCompleted → PageCompleted            │
│  TaskCreated → TaskCompleted → JobOrphaned → JobRequeued     │
│  PageStatusChanged                                            │
└──────┬────────────┬──────────────┬─────────────────┬────────┘
       │            │              │                 │
┌──────▼──┐  ┌─────▼──┐  ┌───────▼────┐  ┌─────────▼───────┐
│Evaluator│  │Pipeline│  │Collaboration│  │    Output       │
│ prescan │  │9-phase │  │ SKIP LOCKED │  │ IncrementalImport│
│ routing │  │ chain  │  │ SLA 4-tier  │  │ import_dedup    │
│ scoring │  │ LLM×6  │  │ SmartDispatch│  │ Backpressure   │
└─────────┘  └────────┘  └────────────┘  └────────┬────────┘
                                                    │
┌───────────────────┐  ┌────────────────────────────▼────────┐
│   LLM Adapter     │  │          Feedback                    │
│ Multi-model       │  │ FewShotSyncer (双人共识)             │
│ Circuit Breaker   │  │ CalibrationEngine (±10%限幅)         │
│ Budget Guard      │  │ GoldenSetEvaluator (F1/Binding/HR)  │
│ Prompt Enricher   │  │ ScheduledTaskRunner (6 periodic)     │
└───────────────────┘  └─────────────────────────────────────┘
```

## 核心事件链

```
POST /uploads (TUS) → POST /jobs
  ↓ JobCreated
Evaluator: prescan → score → route (AUTO/HYBRID/HUMAN_ALL)
  ↓ EvaluationCompleted
Pipeline Orchestrator:
  统一并行处理 (Semaphore=PIPELINE_CONCURRENCY, 默认5)
  每页独立DB会话, CrossPageMerger per-job 加锁
  PageProcessor 9-phase:
    1.PDF解析 (pdfplumber→PyMuPDF→OCR fallback)
    2.图片预处理
    3.特征提取 (text_density, price/model pattern)
    4.跨页表格检测
    5.页面分类 (rule fast-path + LLM)
    6.SKU提取 (two-stage → single-stage → fallback)
    7.ID分配 (坐标排序)
    8.图文绑定 (距离+歧义检测)
    9.校验+导出
  ↓ PageCompleted
Output._handler → IncrementalImporter:
  import_dedup 幂等 → ImportAdapter (Idempotency-Key)
  背压检查 (failure_rate>20% → throttle)
  ↓ PageStatusChanged
ReconciliationPoller:
  ASSUMED→CONFIRMED | FAILED滞留→SKIPPED
  Job终态: 条件UPDATE (并发保护)

[人工分支]
Pipeline needs_review → TaskCreated
  → LockManager.acquire_next (FOR UPDATE SKIP LOCKED)
  → heartbeat 30s → complete/skip/revert
  → SLAScanner 四级熔断 (15min→30min→2h→3h)
  ↓ TaskCompleted
  → Output._handler (重导入)
  → Feedback._handler → FewShotSyncer (双人共识)

[定时任务]
每5min:  SLA 熔断扫描
每2min:  锁超时扫描
每30min: 对账轮询
每日2:00: 属性升级检查
每日3:00: 阈值校准 (安全护栏)
每日6:00: 审批超时提醒
```

## ORM 模型 (18 表)

| 表 | 职责 |
|---|------|
| pdf_jobs | Job 主表 (双状态: internal + user_facing) |
| pages | 页面级处理状态 |
| skus | 提取的 SKU + 属性 |
| images | 提取的图片 + 质量评估 |
| sku_image_bindings | SKU-图片绑定关系 |
| human_tasks | 人工任务 (SKIP LOCKED) |
| annotations | 标注记录 |
| state_transitions | 状态变更审计 |
| annotation_examples | Few-shot 样本库 |
| annotator_profiles | 标注员画像 |
| threshold_profiles | 阈值配置版本 |
| calibration_records | 校准建议 (PENDING→APPROVED) |
| eval_reports | Golden Set 评测报告 |
| import_dedup | 导入幂等去重 |
| custom_attr_upgrades | 属性升级候选 |
| checkpoints | Pipeline 断点续传 |
| config_snapshots | 配置冻结快照 |
| eval_cache_entries | 评估缓存 |

## 关键设计约束

| ID | 约束 | 实现 |
|----|------|------|
| C1 | 并行安全跨页合并 | CrossPageMerger per-job asyncio.Lock |
| C2 | 终态=import_status | ReconciliationPoller._check_job_completion |
| C3 | import_dedup幂等 | IncrementalImporter._check_dedup |
| C4 | gather+exception scan | Orchestrator._process_parallel |
| C6 | SKU valid/invalid | ConsistencyValidator.enforce_sku_validity |
| C7 | 最终兜底 | PageProcessor (needs_review=true) |
| C11 | 图片去重后绑定 | SKUImageBinder (dedup filter) |
| C12 | SKU ID坐标排序 | SKUIdGenerator (bbox_y1 primary) |
| C13 | LLM≤6次/页 | PageProcessor.MAX_LLM_CALLS_PER_PAGE |
| C15 | binding_method推断 | SKUImageBinder._infer_method |

## 统计

- **生产代码**: ~10,300 行
- **测试代码**: ~2,300 行
- **API 端点**: 47 (+2: 图片服务、页面详情)
- **ORM 模型**: 18 表
- **事件类型**: 8
- **定时任务**: 6

## V0.2.0 变更摘要 (2026-02-21)

| 变更 | 说明 |
|------|------|
| Pipeline 并行化 | 删除串行/分片模式，统一 Semaphore 并行（默认5并发），18页 PDF 处理时间 ~22min → ~5min |
| CrossPageMerger 加锁 | cache_page/find_continuation 改为 async + per-job Lock，保障并行安全 |
| Orchestrator 重构 | 删除 _process_sequential/_process_chunked，每页独立 DB session |
| Job 详情增强 | 新增 GET /jobs/{id}/images/{image_id}、GET /jobs/{id}/pages/{n}/detail 端点 |
| SKU 图片绑定 | GET /jobs/{id}/skus 返回 images 数组（JOIN sku_image_bindings） |
| 商品导入配置 UI | 前端新增 /config/import 页面 + importConfigStore (localStorage 持久化) |
| SKU 属性展示 | SKUList 组件支持点击展开全部属性，兼容 model_number/product_name 字段名 |
