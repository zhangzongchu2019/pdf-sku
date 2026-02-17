"""
导入适配层。对齐: Output 详设 §4.2

- 幂等键: {sku_id}_v{revision}
- 4xx 分类: 400→数据错误(不重试), 409→CAS重试, 429→长退避
- [P1-O9] 429 退避: 30s/60s/120s
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class ImportResult:
    confirmed: bool = False
    status_code: int = 0
    error: str | None = None


class ImportDataError(Exception):
    """4xx 数据错误 (不重试)。"""
    pass


class ImportServerError(Exception):
    """5xx 服务端错误。"""
    pass


class ImportAdapter:
    MAX_RETRIES = 3
    TIMEOUT = 30
    BACKOFF_429 = [30, 60, 120]
    BACKOFF_5XX = [2, 4, 8]
    MAX_BACKOFF = 300

    def __init__(self, import_url: str = "", check_url: str = ""):
        self._import_url = import_url
        self._check_url = check_url

    async def import_sku(
        self,
        payload: dict,
        image_uris: list[str] | None = None,
        revision: int = 1,
    ) -> ImportResult:
        """导入单个 SKU (幂等)。"""
        if not self._import_url:
            # 无下游 → 直接 ASSUMED
            logger.debug("import_no_downstream", sku_id=payload.get("sku_id"))
            return ImportResult(confirmed=False, status_code=202)

        idempotency_key = f"{payload.get('sku_id', 'unknown')}_v{revision}"

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    resp = await client.post(
                        self._import_url,
                        json={**payload, "image_uris": image_uris or []},
                        headers={
                            "Idempotency-Key": idempotency_key,
                            "X-API-Version": "v1",
                        },
                    )
                    if resp.status_code in (200, 201):
                        return ImportResult(confirmed=True, status_code=resp.status_code)
                    elif resp.status_code == 202:
                        return ImportResult(confirmed=False, status_code=202)
                    elif resp.status_code == 409:
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(min(1 * (2 ** attempt), self.MAX_BACKOFF))
                            continue
                    elif resp.status_code == 429:
                        delay = (self.BACKOFF_429[attempt]
                                 if attempt < len(self.BACKOFF_429)
                                 else self.MAX_BACKOFF)
                        logger.warning("import_rate_limited", attempt=attempt, delay=delay)
                        await asyncio.sleep(delay)
                        continue
                    elif 400 <= resp.status_code < 500:
                        raise ImportDataError(f"4xx: {resp.status_code} - {resp.text[:200]}")
                    else:
                        if attempt < self.MAX_RETRIES:
                            delay = (self.BACKOFF_5XX[attempt]
                                     if attempt < len(self.BACKOFF_5XX)
                                     else self.MAX_BACKOFF)
                            await asyncio.sleep(delay)
                            continue
                        raise ImportServerError(f"5xx: {resp.status_code}")

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.BACKOFF_5XX[min(attempt, 2)])
                    continue
                raise ImportServerError(f"Connection error: {e}")

        raise ImportServerError("Max retries exceeded")

    async def upsert_sku(
        self, payload: dict, revision: int,
    ) -> ImportResult:
        """Upsert: 冲正已导入的 SKU 属性。"""
        if not self._import_url:
            return ImportResult(confirmed=False, status_code=202)

        idempotency_key = f"{payload.get('sku_id', 'unknown')}_v{revision}"
        async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
            resp = await client.put(
                f"{self._import_url}/{payload.get('sku_id', '')}",
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
            if resp.status_code in (200, 201):
                return ImportResult(confirmed=True, status_code=resp.status_code)
            raise ImportServerError(f"Upsert failed: {resp.status_code}")

    async def check_status(
        self, job_id: str, page_number: int,
    ) -> bool | None:
        """检查导入状态 (I5 降级返回 None)。"""
        if not self._check_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._check_url}?job_id={job_id}&page={page_number}")
                if resp.status_code == 200:
                    return resp.json().get("confirmed", False)
            return None
        except Exception:
            return None
