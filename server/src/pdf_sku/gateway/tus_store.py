"""TUS 存储后端: Redis 元数据 + 磁盘文件。对齐: Gateway 详设 §5.1"""
from __future__ import annotations
import os
import time
from pathlib import Path
from nanoid import generate as nanoid  # type: ignore[import-untyped]
from redis.asyncio import Redis
import structlog

logger = structlog.get_logger()

TUS_UPLOAD_DIR = Path(os.environ.get("TUS_UPLOAD_DIR", "/data/tus-uploads"))
TUS_REDIS_PREFIX = "tus:"
TUS_EXPIRE_SECONDS = 86400  # 24h


class TusStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        TUS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def create(self, upload_length: int, metadata: dict[str, str]) -> str:
        upload_id = f"upl_{nanoid(size=21)}"
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        await self._redis.hset(key, mapping={
            "upload_length": str(upload_length),
            "offset": "0",
            "filename": metadata.get("filename", "unknown.pdf"),
            "filetype": metadata.get("filetype", "application/pdf"),
            "status": "uploading",
            "created_at": str(time.time()),
        })
        await self._redis.expire(key, TUS_EXPIRE_SECONDS)
        # 创建磁盘文件 (预分配)
        file_path = TUS_UPLOAD_DIR / upload_id
        file_path.touch()
        logger.info("tus_upload_created", upload_id=upload_id, length=upload_length)
        return upload_id

    async def get_offset(self, upload_id: str) -> int:
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        offset = await self._redis.hget(key, "offset")
        if offset is None:
            raise FileNotFoundError(f"Upload {upload_id} not found")
        return int(offset)

    async def get_metadata(self, upload_id: str) -> dict:
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        data = await self._redis.hgetall(key)
        if not data:
            raise FileNotFoundError(f"Upload {upload_id} not found")
        return {
            "upload_length": int(data["upload_length"]),
            "offset": int(data["offset"]),
            "filename": data["filename"],
            "filetype": data.get("filetype", ""),
            "status": data.get("status", "uploading"),
        }

    async def append(self, upload_id: str, offset: int, chunk: bytes) -> int:
        file_path = TUS_UPLOAD_DIR / upload_id
        with open(file_path, "r+b" if file_path.stat().st_size > 0 else "wb") as f:
            f.seek(offset)
            f.write(chunk)
        new_offset = offset + len(chunk)
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        await self._redis.hset(key, "offset", str(new_offset))
        return new_offset

    async def mark_complete(self, upload_id: str) -> None:
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        await self._redis.hset(key, "status", "complete")

    def get_file_path(self, upload_id: str) -> Path:
        return TUS_UPLOAD_DIR / upload_id

    async def delete(self, upload_id: str) -> None:
        key = f"{TUS_REDIS_PREFIX}{upload_id}"
        await self._redis.delete(key)
        file_path = TUS_UPLOAD_DIR / upload_id
        if file_path.exists():
            file_path.unlink()

    async def cleanup_expired(self, max_age_hours: int = 6) -> int:
        """清理超时未完成的上传。"""
        now = time.time()
        cleaned = 0
        for file_path in TUS_UPLOAD_DIR.iterdir():
            upload_id = file_path.name
            key = f"{TUS_REDIS_PREFIX}{upload_id}"
            data = await self._redis.hgetall(key)
            if not data:
                # Redis 已过期但文件还在
                file_path.unlink(missing_ok=True)
                cleaned += 1
                continue
            if data.get("status") == "complete":
                continue
            created = float(data.get("created_at", "0"))
            if now - created > max_age_hours * 3600:
                await self.delete(upload_id)
                cleaned += 1
        if cleaned:
            logger.info("tus_cleanup", cleaned=cleaned)
        return cleaned
