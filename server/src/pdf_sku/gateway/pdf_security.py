"""PDF 安全检查（进程池隔离）。对齐: Gateway 详设 §5.3"""
from __future__ import annotations
import asyncio
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class SecurityResult:
    safe: bool
    security_issues: list[str] = field(default_factory=list)


class PDFSecurityChecker:
    MAX_PARSE_TIMEOUT = 30  # 秒

    def __init__(self, process_pool: ProcessPoolExecutor | None = None) -> None:
        self._pool = process_pool or ProcessPoolExecutor(max_workers=2)

    async def check(self, file_path: str) -> SecurityResult:
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(self._pool, self._parse_and_check, file_path),
                timeout=self.MAX_PARSE_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error("pdf_security_timeout", file_path=file_path)
            return SecurityResult(safe=False, security_issues=["parse_timeout"])
        except Exception as e:
            logger.error("pdf_security_error", file_path=file_path, error=str(e))
            return SecurityResult(safe=False, security_issues=[f"parse_failed: {e}"])

        logger.info("pdf_security_checked", safe=result.safe,
                     issues=result.security_issues or None)
        return result

    @staticmethod
    def _parse_and_check(file_path: str) -> SecurityResult:
        """在子进程中执行，与主进程内存隔离。"""
        import fitz

        issues: list[str] = []
        doc = fitz.open(file_path)

        try:
            # 1. 加密检测
            if doc.is_encrypted:
                issues.append("encrypted_pdf")

            # 2. JavaScript 注入 — 文档级
            doc_js = doc.get_js()
            if doc_js:
                issues.append("javascript_embedded")

            # 3. JavaScript — Widget 注解级 (抽查前50页)
            if "javascript_embedded" not in issues:
                for page_no in range(min(doc.page_count, 50)):
                    page = doc[page_no]
                    for annot in page.annots() or []:
                        if annot.type[0] == 20:  # PDF_ANNOT_WIDGET
                            xref = annot.xref
                            obj_str = doc.xref_object(xref)
                            if "/JS" in obj_str or "/JavaScript" in obj_str:
                                issues.append("javascript_embedded")
                                break
                    if "javascript_embedded" in issues:
                        break

            # 4. 对象数 (PDF炸弹检测)
            xref_len = doc.xref_length()
            if xref_len > 500_000:
                issues.append("object_count_exceeded")

        finally:
            doc.close()

        return SecurityResult(safe=len(issues) == 0, security_issues=issues)
