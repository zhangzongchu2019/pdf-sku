"""MinIO 存储实现。对齐: 接口契约 §2.9 StorageProvider"""
from __future__ import annotations
import io
from minio import Minio
from minio.error import S3Error
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()


class MinioStorageProvider:
    def __init__(self) -> None:
        self._client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._bucket = settings.minio_bucket

    async def ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)
            logger.info("minio_bucket_created", bucket=self._bucket)

    async def save_file(self, path: str, data: bytes) -> str:
        self._client.put_object(
            self._bucket, path, io.BytesIO(data), length=len(data),
        )
        return f"{self._bucket}/{path}"

    async def save_file_from_path(self, object_name: str, file_path: str) -> str:
        self._client.fput_object(self._bucket, object_name, file_path)
        return f"{self._bucket}/{object_name}"

    async def read_file(self, path: str) -> bytes:
        resp = self._client.get_object(self._bucket, path)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    async def delete_file(self, path: str) -> bool:
        try:
            self._client.remove_object(self._bucket, path)
            return True
        except S3Error:
            return False

    async def get_url(self, path: str, expires: int = 3600) -> str:
        from datetime import timedelta
        return self._client.presigned_get_object(
            self._bucket, path, expires=timedelta(seconds=expires),
        )
