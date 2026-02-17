"""
通知服务 (企微/钉钉 webhook)。对齐: Collaboration 详设 [P1-C2]

支持渠道: supervisor (企微), team (钉钉), system (日志)
"""
from __future__ import annotations
import httpx
import structlog

logger = structlog.get_logger()


class Notifier:
    def __init__(self, wecom_url: str = "", dingtalk_url: str = ""):
        self._webhooks = {
            "supervisor": wecom_url,
            "team": dingtalk_url,
        }

    async def send(
        self, channel: str, message: str, level: str = "INFO",
    ) -> bool:
        """发送通知。"""
        url = self._webhooks.get(channel, "")
        if not url:
            logger.info("notification_logged", channel=channel, message=message)
            return True

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                if "qyapi.weixin" in url:
                    # 企业微信
                    payload = {"msgtype": "text", "text": {"content": f"[{level}] {message}"}}
                else:
                    # 钉钉
                    payload = {"msgtype": "text", "text": {"content": f"[{level}] {message}"}}
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error("notification_failed", channel=channel, error=str(e))
            return False
