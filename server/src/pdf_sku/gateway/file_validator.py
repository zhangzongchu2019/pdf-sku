"""文件校验器。对齐: Gateway 详设 §5.2"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()


@dataclass
class ValidationError:
    code: str
    message: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    file_size_mb: float = 0.0
    page_count: int | None = None
    mime_type: str = ""


class FileValidator:
    MAX_PAGES = 1000  # 对齐 BRD FR-1.1

    async def validate(self, file_path: Path) -> ValidationResult:
        errors: list[ValidationError] = []
        page_count = None

        # 1. MIME (magic bytes)
        mime = self._check_mime(file_path)
        if mime != "application/pdf":
            errors.append(ValidationError("INVALID_MIME", f"Expected PDF, got {mime}"))

        # 2. 页数 (快速读取，不渲染)
        if not errors:
            try:
                with fitz.open(str(file_path)) as doc:
                    page_count = doc.page_count
                if page_count > self.MAX_PAGES:
                    errors.append(ValidationError(
                        "PAGE_COUNT_EXCEEDED", f"{page_count} > {self.MAX_PAGES}"))
                if page_count == 0:
                    errors.append(ValidationError("EMPTY_PDF", "No pages"))
            except Exception as e:
                errors.append(ValidationError("PDF_PARSE_ERROR", str(e)))

        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        result = ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            file_size_mb=file_size_mb,
            page_count=page_count,
            mime_type=mime,
        )
        logger.info("file_validated", valid=result.valid, pages=page_count,
                     size_mb=round(file_size_mb, 2),
                     errors=[e.code for e in errors] if errors else None)
        return result

    @staticmethod
    def _check_mime(path: Path) -> str:
        with open(path, "rb") as f:
            header = f.read(8)
        return "application/pdf" if header[:5] == b"%PDF-" else "application/octet-stream"
