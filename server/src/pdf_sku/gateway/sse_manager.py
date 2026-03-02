"""
SSE 推送引擎。对齐: Gateway 详设 §4.3 + Data Dictionary §4.2

核心设计:
- 每个 Job 级别的 SSE 连接维护独立 asyncio.Queue (maxsize=100)
- EventBus 订阅 → queue.put → SSE 输出
- 心跳 30s / 背压溢出丢弃最旧事件
- Job 终态自动关闭流
"""
from __future__ import annotations
import asyncio
import time
from collections import defaultdict
from typing import AsyncGenerator
from datetime import datetime, timezone

from sse_starlette.sse import ServerSentEvent
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.common.enums import SSEEventType, JobInternalStatus
import structlog

logger = structlog.get_logger()

# Job 终态集合 — 触发 SSE 关闭
TERMINAL_STATUSES = {
    JobInternalStatus.FULL_IMPORTED.value,
    JobInternalStatus.CANCELLED.value,
    JobInternalStatus.REJECTED.value,
    JobInternalStatus.EVAL_FAILED.value,
}

HEARTBEAT_INTERVAL = 30  # 秒
QUEUE_MAX_SIZE = 100


class SSEManager:
    """管理所有活跃 SSE 连接。"""

    def __init__(self) -> None:
        # job_id → list[asyncio.Queue]
        self._connections: dict[str, list[asyncio.Queue]] = defaultdict(list)
        self._setup_subscriptions()

    def _setup_subscriptions(self) -> None:
        """订阅 EventBus 事件 → 分发到对应 Job 的 SSE 队列。"""
        for evt in [
            "PageStatusChanged", "JobStatusChanged", "JobFailed",
            "HumanNeeded", "SLAEscalated", "JobDeleted",
        ]:
            event_bus.subscribe(evt, self._dispatch_event)

    async def _dispatch_event(self, data: dict) -> None:
        """将事件路由到对应 job 的所有 SSE 连接队列。"""
        job_id = data.get("job_id", "")
        if not job_id:
            return
        queues = self._connections.get(job_id, [])
        for q in queues:
            if q.full():
                # 背压: 丢弃最旧事件
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                logger.warning("sse_queue_overflow", job_id=job_id)
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                pass

    async def subscribe_job(self, job_id: str) -> AsyncGenerator[ServerSentEvent, None]:
        """
        生成 SSE 事件流。调用方通过 async for 消费。
        产出 ServerSentEvent 对象，由 EventSourceResponse 正确序列化。
        """
        import orjson

        queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._connections[job_id].append(queue)
        logger.info("sse_connected", job_id=job_id,
                     total_conns=len(self._connections[job_id]))

        try:
            # 初始心跳
            yield self._make_sse(SSEEventType.HEARTBEAT, {"ts": _now_iso()})

            while True:
                try:
                    # 等待事件，超时则发心跳
                    data = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)

                    # 映射事件类型
                    sse_event = self._map_event_type(data)
                    yield self._make_sse(sse_event, data)

                    # 检查终态
                    status = data.get("status", "")
                    if status == "DELETED":
                        break
                    if status in TERMINAL_STATUSES:
                        yield self._make_sse(
                            SSEEventType.JOB_COMPLETED if status == JobInternalStatus.FULL_IMPORTED.value
                            else SSEEventType.JOB_FAILED,
                            data,
                        )
                        break

                except asyncio.TimeoutError:
                    # 心跳
                    yield self._make_sse(SSEEventType.HEARTBEAT, {"ts": _now_iso()})

        except asyncio.CancelledError:
            logger.info("sse_cancelled", job_id=job_id)
        finally:
            conns = self._connections.get(job_id)
            if conns is not None:
                try:
                    conns.remove(queue)
                except ValueError:
                    pass
                if not conns:
                    self._connections.pop(job_id, None)
            logger.info("sse_disconnected", job_id=job_id)

    def _map_event_type(self, data: dict) -> str:
        """将 EventBus 事件名映射到 SSE event type。"""
        evt = data.get("_event_type", "")
        mapping = {
            "PageStatusChanged": SSEEventType.PAGE_COMPLETED,
            "JobStatusChanged": SSEEventType.JOB_COMPLETED,
            "JobFailed": SSEEventType.JOB_FAILED,
            "HumanNeeded": SSEEventType.HUMAN_NEEDED,
            "SLAEscalated": SSEEventType.SLA_ESCALATED,
            "JobDeleted": SSEEventType.JOB_DELETED,
        }
        return mapping.get(evt, SSEEventType.HEARTBEAT)

    @staticmethod
    def _make_sse(event_type: str, data: dict) -> ServerSentEvent:
        import orjson
        # 剔除内部字段
        clean = {k: v for k, v in data.items() if not k.startswith("_")}
        json_str = orjson.dumps(clean).decode()
        return ServerSentEvent(data=json_str, event=event_type)

    async def close_and_notify_job(self, job_id: str) -> None:
        """向该 job 所有 SSE 客户端推送 job_deleted 终态事件，并清理连接表。"""
        queues = list(self._connections.get(job_id, []))
        for q in queues:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait({"_event_type": "JobDeleted", "job_id": job_id, "status": "DELETED"})
            except asyncio.QueueFull:
                pass
        # 清空连接表（generator 的 finally 块会处理 queue 自身）
        self._connections.pop(job_id, None)
        logger.info("sse_job_deleted_notified", job_id=job_id, clients=len(queues))

    @property
    def active_connections(self) -> int:
        return sum(len(qs) for qs in self._connections.values())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
