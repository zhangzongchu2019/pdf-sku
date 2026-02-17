"""TUS 1.0.0 协议处理器。对齐: Gateway 详设 §5.1"""
from __future__ import annotations
import base64
import hashlib
from pdf_sku.gateway.tus_store import TusStore
from pdf_sku.common.exceptions import PDFSKUError
import structlog

logger = structlog.get_logger()


class UploadTooLargeError(PDFSKUError):
    code = "UPLOAD_TOO_LARGE"; http_status = 413


class OffsetMismatchError(PDFSKUError):
    code = "OFFSET_MISMATCH"; http_status = 409


class ChecksumFailedError(PDFSKUError):
    code = "CHECKSUM_FAILED"; http_status = 460


class TusHandler:
    SUPPORTED_VERSION = "1.0.0"
    MAX_UPLOAD_SIZE = 16 * 1024 * 1024 * 1024  # 16 GB

    def __init__(self, store: TusStore) -> None:
        self._store = store

    async def handle_creation(self, upload_length: int, metadata: dict[str, str]) -> str:
        if upload_length > self.MAX_UPLOAD_SIZE:
            raise UploadTooLargeError(f"File exceeds {self.MAX_UPLOAD_SIZE // (1024**3)}GB limit")
        filename = metadata.get("filename", "")
        if not filename.lower().endswith(".pdf"):
            raise PDFSKUError("Only PDF files accepted")
        upload_id = await self._store.create(upload_length, metadata)
        return upload_id

    async def handle_head(self, upload_id: str) -> tuple[int, int]:
        meta = await self._store.get_metadata(upload_id)
        return meta["offset"], meta["upload_length"]

    async def handle_patch(
        self, upload_id: str, offset: int, chunk: bytes,
        checksum: str | None = None,
    ) -> tuple[int, bool]:
        current_offset = await self._store.get_offset(upload_id)
        if offset != current_offset:
            raise OffsetMismatchError(
                f"Offset mismatch: expected {current_offset}, got {offset}"
            )
        if checksum:
            self._verify_checksum(chunk, checksum)
        new_offset = await self._store.append(upload_id, offset, chunk)
        meta = await self._store.get_metadata(upload_id)
        is_complete = new_offset >= meta["upload_length"]
        if is_complete:
            await self._store.mark_complete(upload_id)
            logger.info("tus_upload_complete", upload_id=upload_id,
                        size=new_offset, filename=meta["filename"])
        return new_offset, is_complete

    async def handle_delete(self, upload_id: str) -> None:
        await self._store.delete(upload_id)

    @staticmethod
    def _verify_checksum(chunk: bytes, checksum_header: str) -> None:
        parts = checksum_header.split(" ", 1)
        if len(parts) != 2 or parts[0] != "sha1":
            raise ChecksumFailedError(f"Unsupported checksum algorithm: {parts[0] if parts else 'none'}")
        expected = parts[1]
        actual = base64.b64encode(hashlib.sha1(chunk).digest()).decode()
        if actual != expected:
            raise ChecksumFailedError("Checksum mismatch")
