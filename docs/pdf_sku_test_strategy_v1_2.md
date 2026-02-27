# PDF-SKU 提取系统测试策略

> **文档版本**: V1.2  
> **对齐文档**: TA V1.6 · OpenAPI V1.2 · 后端详设 V1.1/V1.2 · 前端详设 V1.0 · UI/UX V1.3 附录 C/F/G  
> **团队配置**: 1 QA 全职 + 开发自测  
> **变更记录**:  
> - V1.2: 合并四模型评审修复（LLM 增强测试、故障注入、跨页表格、Checkpoint 恢复、Shadow Mode 等 43 项）  
> - V1.0: 初始版本

---

## 1. 测试分层策略

```
                    ┌──────────────────┐
                    │   E2E Tests      │  5%   ~25 条关键路径
                    │   (Playwright)   │
                ┌───┴──────────────────┴───┐
                │   Integration Tests      │  25%  ~100 条模块间
                │   (pytest + TestClient)  │
            ┌───┴──────────────────────────┴───┐
            │   Unit Tests                     │  70%  ~300 条
            │   (pytest + Vitest)              │
            └──────────────────────────────────┘
```

| 层级 | 框架 | 覆盖目标 | 执行时机 | Owner |
|------|------|---------|---------|-------|
| Unit（后端） | pytest 8.x + pytest-asyncio | 行 ≥ 80%, 分支 ≥ 70% | 每次 commit | 开发 |
| Unit（前端） | Vitest + React Testing Library | 行 ≥ 75%, 分支 ≥ 65% | 每次 commit | 前端 |
| Integration | pytest + httpx.AsyncClient + testcontainers | 接口契约 + 跨模块流 | 每次 MR | 开发+QA |
| E2E | Playwright + TypeScript | 关键业务路径 | 每日定时 + Release 前 | QA |
| Performance | Locust + k6 | TA §7.4 吞吐量指标 | Sprint 末 | QA |
| Contract | Schemathesis (OpenAPI fuzz) | OpenAPI 规格一致性 | 每次 MR | CI 自动 |
| Chaos | 故障注入（toxiproxy / kill） | 降级链路验证 | 每 Sprint | QA+SRE |
| Shadow | 模型对比测试 | 新老模型切流效果 | 模型更新时 | QA |

---

## 2. 后端单元测试

### 2.1 测试组织

```
tests/
├── unit/
│   ├── auth/                          # [V2.1 新增]
│   │   ├── test_jwt_auth.py
│   │   ├── test_password_hash.py
│   │   └── test_rbac.py
│   ├── gateway/
│   │   ├── test_job_creator.py
│   │   ├── test_pdf_prescan.py
│   │   └── test_file_hash.py
│   ├── evaluator/
│   │   ├── test_route_decision.py
│   │   ├── test_dimension_scoring.py
│   │   └── test_confidence_aggregation.py
│   ├── pipeline/
│   │   ├── test_parser_adapter.py
│   │   ├── test_page_classifier.py
│   │   ├── test_text_classifier.py
│   │   ├── test_image_classifier.py
│   │   ├── test_layout_classifier.py
│   │   ├── test_sku_extractor.py
│   │   └── test_binding_resolver.py
│   ├── llm_adapter/
│   │   ├── test_prompt_builder.py
│   │   ├── test_response_parser.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_rate_limiter.py
│   │   ├── test_budget_tracker.py
│   │   └── test_experiment_router.py
│   ├── collaboration/
│   │   ├── test_task_manager.py
│   │   ├── test_lock_manager.py
│   │   ├── test_sla_escalator.py
│   │   └── test_priority_scorer.py
│   ├── output/
│   │   ├── test_sku_importer.py
│   │   ├── test_dedup_engine.py
│   │   └── test_reconciliation.py
│   ├── feedback/
│   │   ├── test_annotation_collector.py
│   │   ├── test_calibration_trigger.py
│   │   └── test_threshold_adjuster.py
│   └── config/
│       ├── test_config_provider.py
│       └── test_category_schema.py
├── integration/             # §3
├── chaos/                   # §3.3
├── e2e/                     # §5
├── perf/                    # §6
├── fixtures/
│   ├── sample_pdfs/
│   ├── golden_responses/
│   ├── vcr_cassettes/       # V1.2: LLM 录制回放
│   ├── large/               # V1.2: 大规模测试集
│   ├── seed_data/
│   └── conftest.py
└── conftest.py
```

### 2.2 核心用例矩阵

#### Gateway 模块

| 用例 ID | 测试项 | 输入 | 预期 | 优先级 |
|---------|--------|------|------|--------|
| G-U01 | PDF 预扫安全检测 | JS 嵌入 PDF | 拒绝 + security:javascript_embedded | P0 |
| G-U02 | PDF 预扫安全检测 | 加密 PDF | 拒绝 + security:encrypted_pdf | P0 |
| G-U03 | 文件大小上限 | 16.1GB 文件 | 拒绝 413 | P0 |
| G-U04 | 页数上限 | 1001 页 PDF | 拒绝 413 + PAGE_COUNT_EXCEEDED | P0 |
| G-U05 | Hash 去重 | 相同 hash 二次上传 | 409 重复 | P0 |
| G-U06 | 正常创建 Job | 有效 PDF + profile | Job 状态 UPLOADED | P0 |
| G-U07 | 孤儿任务重提 | ORPHANED 状态 Job | 重置为 EVALUATING | P1 |
| G-U08 | 非孤儿重提 | PROCESSING 状态 Job | 409 JOB_NOT_ORPHANED | P1 |

#### Auth 模块 [V2.1 新增]

| 用例 ID | 测试项 | 输入 | 预期 | 优先级 |
|---------|--------|------|------|--------|
| AU-U01 | 登录成功 | 有效用户名/密码 | 200 + JWT token + user 对象 | P0 |
| AU-U02 | 登录失败 | 错误密码 | 401 INVALID_CREDENTIALS | P0 |
| AU-U03 | 注册新用户 | 新用户名 + 密码 + role | 201 + token + user | P0 |
| AU-U04 | 注册重复用户名 | 已存在用户名 | 409 USERNAME_EXISTS | P0 |
| AU-U05 | JWT 有效验证 | 有效 token | 200 /auth/me 返回用户信息 | P0 |
| AU-U06 | JWT 过期 | 过期 token | 401 TOKEN_EXPIRED | P0 |
| AU-U07 | RBAC admin-only | annotator 访问 /auth/users | 403 FORBIDDEN | P0 |
| AU-U08 | 修改密码 | 正确旧密码 + 新密码 | 200 密码已更新 | P1 |
| AU-U09 | 修改密码-旧密码错误 | 错误旧密码 | 400 | P1 |
| AU-U10 | Admin 创建用户 | admin token + 用户信息 | 201 | P1 |
| AU-U11 | Admin 禁用用户 | PATCH /auth/users/{id}/status | is_active=false | P1 |
| AU-U12 | 密码哈希不可逆 | 存储的 password_hash | 非明文 + pbkdf2 格式 | P0 |

#### Evaluator 模块

| 用例 ID | 测试项 | 输入 | 预期 | 优先级 |
|---------|--------|------|------|--------|
| E-U01 | 路由决策-全自动 | C_doc=0.90, A=0.85 | route=AUTO | P0 |
| E-U02 | 路由决策-人机协同 | C_doc=0.60, A=0.85, B=0.40 | route=HYBRID | P0 |
| E-U03 | 路由决策-全人工 | C_doc=0.30, B=0.40 | route=HUMAN_ALL | P0 |
| E-U04 | 页面置信度聚合 | 5 维度分数 + 权重 | 加权平均正确 | P0 |
| E-U05 | 配置冻结快照 | 评估时切换配置 | 使用冻结版本 | P1 |
| E-U06 | 空白页过滤 | blank_ratio=0.95 | 页面标记 BLANK | P1 |

#### LLM Adapter 模块

| 用例 ID | 测试项 | 输入 | 预期 | 优先级 |
|---------|--------|------|------|--------|
| L-U01 | 熔断器-打开 | 连续 5 次失败 | 状态 OPEN + fallback | P0 |
| L-U02 | 熔断器-半开恢复 | OPEN + 30s 后请求 | HALF_OPEN → 1 次试探 | P0 |
| L-U03 | 限速器-Token 桶 | 突发 100 RPM | 超额请求排队 | P0 |
| L-U04 | 预算追踪-超额 | daily_budget 耗尽 | 拒绝 + BUDGET_EXHAUSTED | P0 |
| L-U05 | Prompt 构建 | 页面上下文 + schema | 正确 XML 模板 | P0 |
| L-U06 | 响应解析-正常 | 标准 JSON | 解析出 SKU 属性 | P0 |
| L-U07 | 响应解析-畸形 | 缺字段/格式错误 | 触发 semantic_failure + 重试 | P0 |
| L-U08 | 实验路由 | A/B bucket 配置 | 正确分流到不同模型 | P1 |
| L-U09 | 超时处理 | 30s 无响应 | 触发 timeout + breaker 计数 | P1 |

#### Pipeline 模块

| 用例 ID | 测试项 | 输入 | 预期 | 优先级 |
|---------|--------|------|------|--------|
| P-U01 | 页面分类 | 商品展示页 | page_type=B | P0 |
| P-U02 | 版面分类 | 多品网格页 | layout_type=L2 | P0 |
| P-U03 | SKU 属性提取 | 含型号/尺寸/价格文本 | 6 字段正确提取 | P0 |
| P-U04 | 图文绑定-歧义 | top1-top2 差 < 0.2 | 标记 ambiguous | P0 |
| P-U05 | 图文绑定-确定 | top1-top2 差 ≥ 0.2 | 自动绑定 top1 | P0 |
| P-U06 | 图片质量-不合格 | short_edge < 640px | search_eligible=false | P0 |
| P-U07 | Parser 降级 | 主 parser 超时 | 切换 fallback parser | P1 |

#### Collaboration / Output / Config 模块

| 用例 ID | 测试项 | 预期 | 优先级 |
|---------|--------|------|--------|
| C-U01 | 锁获取 | PROCESSING + locked_by | P0 |
| C-U02 | 锁冲突 | 409 + locked_by 姓名 | P0 |
| C-U03 | 锁超时 60s | 锁自动释放 | P0 |
| C-U04 | 心跳续期 | 锁持续有效 | P0 |
| C-U05 | SLA 升级 15min | priority → HIGH | P0 |
| C-U06 | SLA 升级 30min | priority → CRITICAL | P0 |
| C-U07 | SLA 自动接受 3h | 自动接受 AI 结果 | P1 |
| C-U08 | 任务撤销 | CREATED | P1 |
| C-U09 | 幂等提交 | 第二次 409 | P1 |
| O-U01 | SKU 去重 | 合并为一条 | P0 |
| O-U02 | 增量导入 | upsert | P0 |
| O-U03 | 对账-确认 | CONFIRMED | P0 |
| O-U04 | 对账-失败 | EXPORT_FAILED + 重试 | P1 |
| CF-U01 | 乐观锁-正常 | 版本递增 | P0 |
| CF-U02 | 乐观锁-冲突 | 409 | P0 |
| CF-U03 | 护栏-B≥A | 拒绝 | P0 |
| CF-U04 | 缓存刷新 | 所有节点生效 | P1 |

### 2.3 LLM 测试增强（V1.2 新增）

#### Prompt Snapshot 测试

```python
def test_classify_page_prompt_snapshot():
    """Prompt 模板变更时 snapshot 自动失败，强制人工确认"""
    builder = PromptBuilder()
    prompt = builder.build_classify_page(MOCK_PAGE_CONTEXT, MOCK_SCHEMA)
    assert prompt == snapshot("classify_page_prompt")
    # 如需更新: pytest --snapshot-update
```

#### Schema 属性测试（Property-based）

```python
from hypothesis import given, strategies as st

@given(st.text(), st.text(), st.floats(min_value=0, max_value=1))
def test_parse_classify_response_structure(page_type, layout_type, confidence):
    """无论 LLM 返回什么文案，解析后的结构必须满足约束"""
    raw = f'{{"page_type": "{page_type}", "layout_type": "{layout_type}", "confidence": {confidence}}}'
    try:
        result = ResponseParser.parse_classify(raw)
        assert result.page_type in ('A', 'B', 'C', 'D') or result.page_type is None
        assert 0.0 <= result.confidence <= 1.0
    except ParseError:
        pass  # 畸形输入允许抛 ParseError

def test_parse_malformed_json_injection():
    """JSON 注入 / 畸形响应不崩溃"""
    malformed_cases = [
        '{"page_type": "B", "extra": "<script>alert(1)</script>"}',
        '{"page_type": "B"',          # 截断
        'I am not JSON at all',        # 纯文本
        '',                            # 空
        '{"page_type": "E"}',          # 非法枚举
    ]
    for raw in malformed_cases:
        result = ResponseParser.safe_parse_classify(raw)
        assert result.is_error or result.page_type in ('A', 'B', 'C', 'D', None)
```

### 2.4 Mock 策略

```python
@pytest.fixture
def mock_llm_client():
    with open("tests/fixtures/golden_responses/classify_page_b.json") as f:
        golden = json.load(f)
    mock = AsyncMock()
    mock.classify_page.return_value = LLMResponse(
        content=golden["content"],
        usage=TokenUsage(input_tokens=500, output_tokens=200),
        model="claude-sonnet-4-20250514", latency_ms=1200)
    return mock

@pytest.fixture
async def db_session():
    async with AsyncSession(engine) as session:
        async with session.begin():
            yield session
            await session.rollback()

@pytest.fixture
def mock_redis():
    import fakeredis.aioredis
    return fakeredis.aioredis.FakeRedis()
```

---

## 3. 集成测试

### 3.1 框架

```python
import pytest
from httpx import AsyncClient, ASGITransport
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()

@pytest.fixture(scope="session")
def redis():
    with RedisContainer("redis:7") as r:
        yield r.get_connection_url()
```

### 3.2 关键集成流

#### 认证流 [V2.1 新增]

```
Step 1: POST /auth/register → 201 注册成功
Step 2: POST /auth/login → 200 获取 JWT token
Step 3: GET /auth/me (Bearer token) → 200 用户信息
Step 4: PATCH /auth/me → 200 更新资料
Step 5: POST /auth/me/change-password → 200
Step 6: 使用无效 token → 401
Step 7: annotator 访问 POST /jobs → 403 (RBAC)
Step 8: uploader 访问 POST /tasks/next → 403 (RBAC)
```

#### 全自动流（Happy Path）

```
Step 1: POST /uploads → 创建上传
Step 2: PATCH /uploads/{id} → 上传文件
Step 3: POST /jobs → 创建 Job → Assert UPLOADED
Step 4: 触发评估 → Assert EVALUATED, route=AUTO
Step 5: 触发处理 → Assert 所有页面 AI_COMPLETED
Step 6: 触发导入 → Assert FULL_IMPORTED, SKU 数量 > 0
```

#### 人机协同流

```
Step 1-4: 同上，Assert route=HYBRID
Step 5: Assert 部分页面 HUMAN_QUEUED
Step 6: GET /tasks?group_by=file → 有待标注任务
Step 7: POST /tasks/{id}/lock → 200
Step 8: POST /tasks/{id}/complete → 提交标注
Step 9: Assert 人工页面 HUMAN_COMPLETED → IMPORTED_CONFIRMED
Step 10: Assert FULL_IMPORTED
```

#### 并发锁冲突

```
Step 1: User A → lock → 200
Step 2: User B → lock → 409 + locked_by=A
Step 3: 60s 无心跳 → 锁释放
Step 4: User B → lock → 200
```

#### 配置热更新

```
Step 1: profile_v1.A=0.85 → route=HYBRID
Step 2: PUT /config → A=0.75
Step 3: POST /config/reload
Step 4: 新 Job → route=AUTO（阈值降低→更多自动）
Assert: 旧 Job frozen_config_version 仍为 v1
```

#### SSE 推送验证

```
Step 1: 建立 SSE 连接
Step 2: 触发页面处理完成
Step 3: Assert 收到 page_completed 事件
Step 4: Assert data 含 { page_no, status, confidence }
```

#### 状态流转完整性

```
Job: UPLOADED → EVALUATING → EVALUATED → PROCESSING → FULL_IMPORTED
Page: PENDING → AI_QUEUED → AI_PROCESSING → AI_COMPLETED → IMPORTED_CONFIRMED
Assert: 每次变更写 state_transitions 表
Assert: 无非法状态跳转
```

### 3.3 故障注入测试（V1.2 新增）

#### LLM 故障传播

```python
class TestLLMFaultInjection:
    async def test_circuit_breaker_triggers_human_fallback(self):
        """LLM 连续 5 次失败 → 熔断 → 路由降级 HUMAN_ALL"""
        mock_llm.side_effect = [LLMError(500)] * 5
        job = await create_test_job()
        await trigger_evaluation(job.id)
        assert circuit_breaker.state == CircuitState.OPEN
        job = await get_job(job.id)
        assert job.route == 'HUMAN_ALL'
        assert job.degrade_reason == 'LLM_CIRCUIT_OPEN'
    
    async def test_timeout_triggers_fallback_parser(self):
        """LLM 超时 → 重试 2 次 → fallback parser"""
        mock_llm.side_effect = [asyncio.TimeoutError()] * 2
        result = await pipeline.process_page(page)
        assert result.parser_backend == 'fallback'
    
    async def test_budget_exhausted_rejects_new_jobs(self):
        """日预算耗尽 → 新 Job 直接降级"""
        budget_tracker.set_remaining(0)
        job = await create_test_job()
        await trigger_evaluation(job.id)
        assert (await get_job(job.id)).degrade_reason == 'BUDGET_EXHAUSTED'
```

#### Redis 故障传播

```python
class TestRedisFaultInjection:
    async def test_redis_disconnect_lock_behavior(self):
        """Redis 短暂断连 3s → 锁仍有效（TTL 未过期）"""
        await task_api.lock(task_id, annotator_a)
        await redis_proxy.disconnect(duration_sec=3)
        await redis_proxy.reconnect()
        assert (await task_api.get_lock_info(task_id)).locked_by == annotator_a
    
    async def test_sentinel_failover(self):
        """Sentinel 主从切换 → 应用 < 5s 自动重连"""
        await redis_sentinel.failover('pdf-sku-master')
        await asyncio.sleep(5)
        assert (await task_api.lock(task_id, annotator_b)).status_code == 200
```

#### 数据库故障

```python
class TestDatabaseFaultInjection:
    async def test_connection_pool_exhausted(self):
        """连接池耗尽 → 5s 内返回 503"""
        connections = [await pool.acquire() for _ in range(20)]
        with pytest.raises(ServiceUnavailable):
            await asyncio.wait_for(task_api.get_task(task_id), timeout=5)
        for conn in connections:
            await pool.release(conn)
        assert (await task_api.get_task(task_id)).status_code == 200
```

#### Chaos 执行计划

| 故障场景 | 注入方式 | 频率 | 预期行为 | 验收标准 |
|---------|---------|------|---------|---------|
| LLM API 全部 500 | Mock / 错误 Key | 每 Sprint | 熔断 → 全人工 | 降级 < 30s |
| LLM 延迟 10s | toxiproxy | 每 Sprint | 超时 → fallback | 页面完成 |
| Redis 主宕机 | kill | 每月 | Sentinel 切主 < 5s | 自动重连 |
| PG 主重启 | delete pod | 每月 | pgBouncer 重连 | API 503 < 10s |
| Worker OOM | memory limit 设低 | 每 Sprint | Pod 重启 + PEL 恢复 | 任务不丢失 |
| 网络分区 | NetworkPolicy 阻断 | 每季度 | 锁降级 + 告警 | 友好提示 |

### 3.4 业务特有集成测试（V1.2 新增）

#### 跨页表格拼接（对齐 BRD FR-2.6）

```python
class TestCrossPageTableMerge:
    async def test_three_page_continuation_table(self):
        """3 页续表 → 正确合并为单一 SKU 列表"""
        job = await create_job_from_fixture("pdf_cross_page_table.pdf")
        await process_job(job.id)
        xskus = await get_cross_page_skus(job.id)
        assert len(xskus) >= 1
        for xsku in xskus:
            assert len(xsku.fragments) >= 2
```

#### DEGRADED_HUMAN 终态（对齐 BA §5.1）

```python
class TestDegradedHumanCompletion:
    async def test_degraded_to_full_imported(self):
        """预筛拒绝 → 全人工 → 逐页完成 → FULL_IMPORTED"""
        mock_evaluator.return_value = EvalResult(route='HUMAN_ALL', degrade_reason='prescan_reject')
        job = await create_test_job()
        await trigger_evaluation(job.id)
        assert (await get_job(job.id)).status == 'DEGRADED_HUMAN'
        
        for page in await get_pages(job.id):
            task = await lock_task(page.task_id)
            await complete_task(task.id, mock_payload())
        
        assert (await get_job(job.id)).status == 'FULL_IMPORTED'
```

### 3.5 Checkpoint 恢复测试（V1.2 新增）

```python
class TestCheckpointRecovery:
    async def test_worker_crash_recovery(self):
        """处理 50 页 → 第 25 页后宕机 → 恢复后从第 26 页继续"""
        job = await create_job_from_fixture("pdf_50pages.pdf")
        with patch_worker_crash_after_pages(25):
            await process_job(job.id)
        
        checkpoints = await db.fetch_all(
            "SELECT page_no FROM checkpoints WHERE job_id = ? AND stage = 'PAGE_COMPLETED'", job.id)
        assert len(checkpoints) == 25
        
        await scan_orphan_jobs()
        await wait_for_job_completion(job.id, timeout=120)
        
        # 验证没有重复处理
        all_cp = await db.fetch_all(
            "SELECT page_no, COUNT(*) as cnt FROM checkpoints "
            "WHERE job_id = ? AND stage = 'PAGE_COMPLETED' GROUP BY page_no", job.id)
        for cp in all_cp:
            assert cp.cnt == 1
```

### 3.6 业务不变量回归测试（V1.2 新增）

```python
class TestRouteStatusInvariants:
    async def test_auto_route_no_degrade_reason(self):
        """route=AUTO 时 degrade_reason 必须为 null"""
        job = await create_auto_route_job()
        assert job.route == 'AUTO' and job.degrade_reason is None
    
    async def test_search_eligible_iff_short_edge_ge_640(self):
        """INV-03: search_eligible ↔ short_edge ≥ 640"""
        for img in (await get_skus_with_images(job.id)):
            assert img.search_eligible == (img.short_edge_px >= 640)

class TestSLAFourLevelEscalation:
    async def test_15min_high(self): ...
    async def test_30min_critical(self): ...
    async def test_2h_auto_resolve(self): ...
    async def test_3h_auto_accept(self):
        """3h 超时 → 自动接受 AI 结果 → IMPORTED_ASSUMED"""
        task = await create_human_task()
        await advance_time(hours=3, minutes=1)
        assert (await get_task(task.id)).status == 'AUTO_ACCEPTED'
```

### 3.7 Pipeline Fallback + 预筛热更新（V1.2 新增）

```python
class TestTwoStageFallback:
    async def test_high_failure_rate_triggers_single_stage(self):
        """两阶段失败率 > 30% → 回退单阶段"""
        mock_llm.side_effect = create_partial_failure_responses(total=10, fail_count=4)
        await process_job(job.id)
        pages = await get_pages(job.id)
        for page in pages[4:]:
            assert page.parser_backend == 'single_stage'

class TestPrescanConfigHotReload:
    async def test_prescan_rule_change(self):
        """预筛规则热更新后新 Job 受影响"""
        await update_config(prescan_rules={'javascript_embedded': 'warn'})
        job1 = await create_job("js_embedded.pdf")
        assert (await get_job(job1.id)).status != 'EVAL_FAILED'
        
        await update_config(prescan_rules={'javascript_embedded': 'reject'})
        await reload_config()
        job2 = await create_job("js_embedded.pdf")
        assert (await get_job(job2.id)).status == 'EVAL_FAILED'
```

### 3.8 不变量验证（对齐接口契约总表 9 条）

| ID | 不变量 | 验证方式 |
|----|--------|---------|
| INV-01 | Job 终态不可逆 | 修改 FULL_IMPORTED → Assert 拒绝 |
| INV-02 | 活跃 profile 唯一 | 同时激活 2 个 → Assert 旧 profile 自动去激活 |
| INV-03 | search_eligible ↔ short_edge≥640 | 导入后查 images 表 |
| INV-04 | page_number 唯一性 | 重复插入 → Assert 约束拒绝 |
| INV-05 | 同一元素不属多组 | 提交含重复 element_id → Assert 400 |
| INV-06 | ungrouped ∩ grouped = ∅ | 提交交叉 → Assert 400 |
| INV-07 | bbox 归一化 0~1 | 提交 bbox.x=1.5 → Assert 400 |
| INV-08 | 完整 SKU model∪name ≠ ∅ | 空 model + 空 name → Assert 400 |
| INV-09 | 锁定任务仅锁定者可提交 | User B 提交 A 锁定的任务 → Assert 409 |

---

## 4. 前端单元测试

### 4.1 框架

```typescript
// vitest.config.ts
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      thresholds: { lines: 75, branches: 65, functions: 75 },
    },
  },
});
```

### 4.2 核心用例

```typescript
// Store 测试
describe('annotationStore', () => {
  it('createGroup: 从未分组元素创建分组', () => { ... });
  it('buildSubmitPayload: 正确构建提交数据', () => { ... });
});

describe('undoStore', () => {
  it('30 步栈深度限制', () => { ... });
  it('新操作清空 redoStack', () => { ... });
});

// Canvas 引擎测试
describe('LassoGeometry', () => {
  it('containsPoint: 射线法判断', () => { ... });
  it('captureElements: 中心点在多边形内', () => { ... });
});

describe('CoordinateSystem', () => {
  it('归一化 ↔ 屏幕坐标双向转换一致', () => { ... });
});

// Hook 测试
describe('useHeartbeat', () => {
  it('每 30s 发送一次心跳', () => { ... });
  it('visibilitychange 恢复时立即补发', () => { ... });
});
```

---

## 5. E2E 测试

### 5.1 框架

```typescript
export default defineConfig({
  testDir: './e2e',
  retries: 1,
  workers: 2,
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
  ],
});
```

### 5.2 关键路径用例

| 用例 ID | 路径 | 断言 | 优先级 |
|---------|------|------|--------|
| E2E-00 | 登录 → 角色首页 [V2.1] | 未登录→/login, 输入凭据, uploader→/dashboard, annotator→/annotate | P0 |
| E2E-00a | Admin 用户管理 [V2.1] | /admin/users 创建用户 → 列表显示 → 禁用/启用 | P1 |
| E2E-01 | PDF 上传 → Job 创建 | 进度 100% + toast | P0 |
| E2E-02 | 标注完整流程 | 提交确认 → toast "已提取 N 个 SKU" | P0 |
| E2E-03 | 标注快捷键 | V/L/G/1~4/Ctrl+Z/Ctrl+Enter | P0 |
| E2E-04 | 看板筛选+批量操作 | 状态更新 + toast | P1 |
| E2E-05 | 配置编辑+护栏 | B≥A 红色提示 + 禁止保存 | P0 |
| E2E-06 | 锁冲突体验 | B 收到冲突提示 | P0 |
| E2E-07 | SSE 实时推送 | 进度条递增 | P1 |
| E2E-08 | 1000 页虚拟滚动 | ≥ 55fps | P1 |
| E2E-09 | 响应式-最小宽度 | 1023px 不可用提示 | P1 |
| E2E-10 | 新手引导 | 5 步引导 | P2 |
| E2E-11 | 心跳丢失恢复 | 断网 60s → 锁释放 → 重新 lock | P0 |
| E2E-12 | 浏览器关闭 | 60s 后 B 可接管 | P0 |
| E2E-13 | Tab 切换降频 | 切回 1s 内补发心跳 | P1 |
| E2E-14 | 并发提交竞态 | 第一个成功，第二个 409 | P0 |
| E2E-15 | SLA 自动接受 | 3h → PARTIAL_IMPORTED | P1 |
| E2E-16 | 绑定歧义人工确认 | resolved=true + selected_rank | P0 |
| E2E-17 | 绑定歧义跳过 | 提交警告弹窗 | P1 |

---

## 6. 性能测试

### 6.1 后端 API 基准（对齐 TA §7.4）

| 接口 | P50 | P99 | 并发 | 持续 |
|------|-----|-----|------|------|
| POST /jobs | < 200ms | < 1s | 10 | 5min |
| GET /jobs | < 100ms | < 500ms | 50 | 5min |
| POST /tasks/{id}/lock | < 50ms | < 200ms | 20 | 5min |
| POST /tasks/{id}/heartbeat | < 30ms | < 100ms | 100 | 5min |
| POST /tasks/{id}/complete | < 300ms | < 1s | 10 | 5min |
| impact-preview | < 500ms | < 2s | 5 | 5min |
| SSE 事件延迟 | < 500ms | < 2s | 50连接 | 10min |

### 6.2 前端性能基准（对齐 UI/UX 附录 G）

| 场景 | 指标 | 目标 |
|------|------|------|
| /annotate 首屏 | FCP | < 2.0s |
| /annotate 首屏 | TTI | < 2.5s |
| 页面切换（缓存） | 渲染时间 | < 300ms |
| 套索 → 分组 | 响应时间 | < 100ms |
| 1000 页滚动 | FPS | ≥ 55 |
| 缩放 30%~300% | FPS | ≥ 55 |
| Ctrl+Z 撤销 | UI 更新 | < 50ms |
| 2h 连续使用 | 内存增长 | < 100MB |

### 6.3 Worker Pipeline 压测（V1.2 新增）

| 指标 | 方法 | 基线目标 |
|------|------|---------|
| 单 Pod 吞吐 | 100 Job / 1 Worker | ≥ 15 Job/min |
| HPA 扩容响应 | 队列 > 50 | 新 Pod Ready < 60s |
| 队列积压曲线 | Grafana redis_queue_depth | 峰值 < 200 |
| 扩容线性度 | 1→3→6 Pod | > 80% 效率 |

---

## 7. Contract 测试（OpenAPI Fuzz）

```yaml
- name: OpenAPI Contract Test
  run: |
    schemathesis run \
      --url http://localhost:8000/openapi.json \
      --hypothesis-max-examples=100 \
      --stateful=links \
      --checks all \
      --validate-schema=true
```

**错误码白名单**：4xx（业务错误）可接受，5xx 不可接受。

---

## 8. CI/CD 集成

### 8.1 Pipeline

```
Commit → Lint+TypeCheck → Unit Test → Integration → Build → Staging → E2E → Production
 <3min     <3min          <5min       <10min                <30min
```

### 8.2 质量门禁

| 阶段 | 检查项 | 阈值 | 阻断 |
|------|--------|------|------|
| Commit | ESLint + mypy + ruff | 0 error | ✅ |
| MR | 后端行覆盖率 | ≥ 80% | ✅ |
| MR | 后端分支覆盖率 | ≥ 70% | ✅ |
| MR | 前端行覆盖率 | ≥ 75% | ✅ |
| MR | 前端分支覆盖率 | ≥ 65% | ✅ |
| MR | Contract test | 0 failure (5xx) | ✅ |
| MR | 集成测试 P0 | 全部通过 | ✅ |
| Nightly | E2E P0 | 全部通过 | 告警 |
| Release | 性能基准 | 不超预算 150% | ✅ |
| Release | Lighthouse | ≥ 80 | ✅ |

---

## 9. 测试数据管理

### 9.1 固定测试集

```
tests/fixtures/
├── sample_pdfs/
│   ├── valid_10pages.pdf
│   ├── valid_1000pages.pdf
│   ├── encrypted.pdf
│   ├── js_embedded.pdf
│   ├── blank_pages.pdf
│   ├── scanned_low_quality.pdf
│   └── mixed_layouts.pdf
├── golden_responses/
│   ├── classify_page_a.json
│   ├── classify_page_b.json
│   ├── extract_sku_complete.json
│   ├── extract_sku_partial.json
│   └── binding_ambiguous.json
├── vcr_cassettes/             # V1.2: LLM VCR 录制
│   └── llm_responses.yaml
├── seed_data/
│   ├── profiles.sql
│   ├── annotators.sql
│   └── merchants.sql
└── large/                     # V1.2: 大规模测试集
    ├── pdf_1000pages.pdf       # 1000 页混合版面
    ├── pdf_500pages_scanned.pdf
    ├── pdf_50sku_complex.pdf   # 20 页 × 50 SKU 含跨页
    ├── pdf_rotated_mixed.pdf
    ├── pdf_multilingual.pdf
    └── README.md
```

### 9.2 Golden Response 录制方法（V1.2 新增）

```python
import vcrpy

@pytest.fixture
def vcr_llm():
    """VCR 模式：首次运行录制真实 LLM 响应，CI 中回放"""
    with vcrpy.VCR(
        cassette_library_dir='tests/fixtures/vcr_cassettes/',
        record_mode='once',
        match_on=['method', 'path'],
        filter_headers=['Authorization'],
    ).use_cassette('llm_responses.yaml'):
        yield
```

CI 中设置 `VCR_RECORD_MODE=none`，不调用真实 API。

### 9.3 数据隔离

每个测试用例使用独立 `test_merchant_id` 前缀。数据库使用事务回滚（单元）或 TRUNCATE + 重新 seed（集成）。

---

## 10. Shadow Mode 测试（V1.2 新增）

对齐 LLM Adapter V1.2 `experiment_bucket`。

```
                    ┌─────────────┐
                    │  请求         │
                    └──────┬──────┘
                    ┌──────▼──────────┐
                    │ Experiment Router│
                    │ control(90%)    │
                    │ shadow(10%)     │
                    └──┬────────┬────┘
                 ┌────▼──┐  ┌──▼────┐
                 │Model A│  │Model B│
                 │(生产) │  │(Shadow)│
                 └──┬────┘  └──┬────┘
                    │          │
                 ┌──▼──────────▼──┐
                 │ 结果对比 Logger  │ ← 仅记录，不影响输出
                 └────────────────┘
```

**对比指标**：

| 指标 | 告警阈值 |
|------|---------|
| 页面分类一致率 | < 90% |
| SKU 数量偏差 | > 20% |
| 平均置信度差 | > 0.1 |
| 延迟比 | > 2.0 |

Staging 环境 10% 流量 × 7 天 → 生成对比报告 → 决定是否切换。

---

## 11. 估算汇总

| 测试类型 | 用例数 | 编写人天 | 维护频率 |
|---------|--------|---------|---------|
| 后端单元测试 | ~200 | 8d | 每 Sprint |
| 前端单元测试 | ~100 | 5d | 每 Sprint |
| 集成测试（含故障注入） | ~100 | 8d | 每 Sprint |
| E2E 测试 | ~25 | 5d | 每 Release |
| 性能测试 | ~15 场景 | 4d | Sprint 末 |
| Contract 测试 | 自动生成 | 1d | 自动 |
| Shadow Mode | 配置 + 报告 | 2d | 模型更新时 |
| **合计** | **~440** | **33d** | — |
