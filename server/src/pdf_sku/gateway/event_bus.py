"""进程内事件总线。生产中可替换为 Redis Stream / NATS。"""
from __future__ import annotations
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
import structlog

logger = structlog.get_logger()

EventHandler = Callable[[dict], Coroutine[Any, Any, None]]


@dataclass
class EventBus:
    """简单的进程内发布/订阅总线。"""
    _subscribers: dict[str, list[EventHandler]] = field(default_factory=lambda: defaultdict(list))

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event_type: str, data: dict) -> None:
        data["_event_type"] = event_type
        data["_timestamp"] = datetime.now(timezone.utc).isoformat()
        handlers = self._subscribers.get(event_type, [])
        for h in handlers:
            try:
                await h(data)
            except Exception:
                logger.exception("event_handler_error", event_type=event_type)


# 全局单例
event_bus = EventBus()
