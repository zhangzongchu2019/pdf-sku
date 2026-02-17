"""
E2E 事件链测试 (纯内存, 无 DB/Redis)。

验证完整事件流:
  JobCreated → Evaluator → EvaluationCompleted → Pipeline → PageCompleted → Output
"""
import asyncio
import pytest
from pdf_sku.gateway.event_bus import EventBus


class EventRecorder:
    """记录所有事件的 helper。"""
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    def handler_for(self, event_type: str):
        async def handler(event: dict):
            self.events.append((event_type, event))
        return handler

    def count(self, event_type: str) -> int:
        return sum(1 for t, _ in self.events if t == event_type)

    def get(self, event_type: str) -> list[dict]:
        return [e for t, e in self.events if t == event_type]


@pytest.mark.asyncio
async def test_full_event_chain():
    """完整事件链: JobCreated → Evaluate → Pipeline → Import。"""
    bus = EventBus()
    recorder = EventRecorder()

    # 注册整条链的模拟处理器
    phases = [
        "JobCreated",
        "EvaluationCompleted",
        "PageCompleted",
        "TaskCreated",
        "TaskCompleted",
    ]
    for phase in phases:
        bus.subscribe(phase, recorder.handler_for(phase))

    # 模拟 Evaluator: JobCreated → EvaluationCompleted
    async def mock_evaluator(event):
        await bus.publish("EvaluationCompleted", {
            "job_id": event["job_id"],
            "route": "AUTO",
            "eval_score": 0.92,
        })
    bus.subscribe("JobCreated", mock_evaluator)

    # 模拟 Pipeline: EvaluationCompleted → PageCompleted
    async def mock_pipeline(event):
        if event.get("route") == "HUMAN_ALL":
            return
        for page in range(1, 4):
            await bus.publish("PageCompleted", {
                "job_id": event["job_id"],
                "page_number": page,
                "status": "AI_COMPLETED",
                "skus": [{"sku_id": f"sku_{page}_001", "validity": "valid"}],
            })
    bus.subscribe("EvaluationCompleted", mock_pipeline)

    # 触发!
    await bus.publish("JobCreated", {
        "job_id": "test-job-001",
        "file_hash": "abc123",
        "total_pages": 3,
    })

    # 让所有异步事件处理完成
    await asyncio.sleep(0.1)

    # 验证
    assert recorder.count("JobCreated") == 1
    assert recorder.count("EvaluationCompleted") == 1
    assert recorder.count("PageCompleted") == 3

    eval_event = recorder.get("EvaluationCompleted")[0]
    assert eval_event["route"] == "AUTO"
    assert eval_event["eval_score"] == 0.92

    pages = recorder.get("PageCompleted")
    assert all(p["status"] == "AI_COMPLETED" for p in pages)
    page_numbers = sorted(p["page_number"] for p in pages)
    assert page_numbers == [1, 2, 3]


@pytest.mark.asyncio
async def test_human_route_event_chain():
    """HUMAN_ALL 路由: JobCreated → Evaluate → TaskCreated (跳 Pipeline)。"""
    bus = EventBus()
    recorder = EventRecorder()

    for phase in ["EvaluationCompleted", "PageCompleted", "TaskCreated"]:
        bus.subscribe(phase, recorder.handler_for(phase))

    async def mock_evaluator(event):
        await bus.publish("EvaluationCompleted", {
            "job_id": event["job_id"],
            "route": "HUMAN_ALL",
            "eval_score": 0.30,
        })
    bus.subscribe("JobCreated", mock_evaluator)

    async def mock_task_creator(event):
        if event.get("route") == "HUMAN_ALL":
            await bus.publish("TaskCreated", {
                "job_id": event["job_id"],
                "task_type": "FULL_MANUAL",
            })
    bus.subscribe("EvaluationCompleted", mock_task_creator)

    await bus.publish("JobCreated", {"job_id": "job-human-001"})
    await asyncio.sleep(0.1)

    assert recorder.count("EvaluationCompleted") == 1
    assert recorder.count("PageCompleted") == 0  # Pipeline 不执行
    assert recorder.count("TaskCreated") == 1


@pytest.mark.asyncio
async def test_task_completion_triggers_import_and_fewshot():
    """TaskCompleted → 同时触发 Import 和 Few-shot。"""
    bus = EventBus()
    recorder = EventRecorder()

    import_triggered = []
    fewshot_triggered = []

    async def mock_import(event):
        import_triggered.append(event)

    async def mock_fewshot(event):
        fewshot_triggered.append(event)

    bus.subscribe("TaskCompleted", mock_import)
    bus.subscribe("TaskCompleted", mock_fewshot)
    bus.subscribe("TaskCompleted", recorder.handler_for("TaskCompleted"))

    await bus.publish("TaskCompleted", {
        "task_id": "task-001",
        "job_id": "job-001",
        "page_number": 5,
        "operator": "annotator_alice",
    })
    await asyncio.sleep(0.05)

    assert len(import_triggered) == 1
    assert len(fewshot_triggered) == 1
    assert recorder.count("TaskCompleted") == 1


@pytest.mark.asyncio
async def test_error_in_one_handler_doesnt_block_others():
    """一个 handler 异常不阻塞其他 handler。"""
    bus = EventBus()
    results = []

    async def bad_handler(event):
        raise RuntimeError("simulated failure")

    async def good_handler(event):
        results.append("success")

    bus.subscribe("Resilience", bad_handler)
    bus.subscribe("Resilience", good_handler)

    await bus.publish("Resilience", {"test": True})
    await asyncio.sleep(0.05)

    assert "success" in results


@pytest.mark.asyncio
async def test_concurrent_jobs():
    """并发多 Job 不互相干扰。"""
    bus = EventBus()
    completed_pages = []

    async def mock_pipeline(event):
        job_id = event["job_id"]
        for p in range(1, 3):
            completed_pages.append({"job_id": job_id, "page": p})

    bus.subscribe("EvaluationCompleted", mock_pipeline)

    # 同时发起 3 个 Job
    await asyncio.gather(
        bus.publish("EvaluationCompleted", {"job_id": "j1", "route": "AUTO"}),
        bus.publish("EvaluationCompleted", {"job_id": "j2", "route": "AUTO"}),
        bus.publish("EvaluationCompleted", {"job_id": "j3", "route": "AUTO"}),
    )
    await asyncio.sleep(0.1)

    assert len(completed_pages) == 6  # 3 jobs × 2 pages
    job_ids = set(p["job_id"] for p in completed_pages)
    assert job_ids == {"j1", "j2", "j3"}
