"""
PDF 解析器 (多库兜底)。对齐: Pipeline 详设 §5.3

策略: pdfplumber → PyMuPDF → OCR-lite (fitz getText)
PaddleOCR 为重依赖，Round 3 预留接口但不强制 import。
"""
from __future__ import annotations
import hashlib
import io
from pathlib import Path
from pdf_sku.pipeline.ir import (
    ParsedPageIR, TextBlock, TableData, ImageInfo, PageMetadata,
)
import structlog

logger = structlog.get_logger()

TEXT_COVERAGE_THRESHOLD = 0.1


class PDFExtractor:
    """多库兜底 PDF 解析器。"""

    def extract(self, file_path: str, page_no: int) -> ParsedPageIR:
        """解析单页 (在进程池中执行)。"""
        # Level 1: pdfplumber
        try:
            result = self._extract_pdfplumber(file_path, page_no)
            if result.text_coverage > TEXT_COVERAGE_THRESHOLD:
                result.parser_backend = "pdfplumber"
                return result
        except Exception as e:
            logger.debug("pdfplumber_fallback", page=page_no, error=str(e))

        # Level 2: PyMuPDF
        try:
            result = self._extract_pymupdf(file_path, page_no)
            if result.text_coverage > TEXT_COVERAGE_THRESHOLD:
                result.parser_backend = "pymupdf"
                return result
        except Exception as e:
            logger.debug("pymupdf_fallback", page=page_no, error=str(e))

        # Level 3: PyMuPDF OCR-lite (text extraction from rendered page)
        result = self._extract_pymupdf_ocr(file_path, page_no)
        result.parser_backend = "pymupdf_ocr"
        return result

    def _extract_pdfplumber(self, path: str, page_no: int) -> ParsedPageIR:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            if page_no < 1 or page_no > len(pdf.pages):
                return ParsedPageIR(page_no=page_no)
            page = pdf.pages[page_no - 1]
            raw_text = page.extract_text() or ""
            text_blocks = self._plumber_text_blocks(page)
            tables = self._plumber_tables(page)
            images = self._plumber_images(page, path, page_no)
            area = max(1.0, float(page.width) * float(page.height))

        return ParsedPageIR(
            page_no=page_no,
            text_blocks=text_blocks,
            tables=tables,
            images=images,
            raw_text=raw_text,
            metadata=PageMetadata(page_width=float(page.width), page_height=float(page.height)),
            reading_order=list(range(len(text_blocks))),
            text_coverage=len(raw_text) / area,
        )

    def _extract_pymupdf(self, path: str, page_no: int) -> ParsedPageIR:
        import fitz
        doc = fitz.open(path)
        try:
            if page_no < 1 or page_no > doc.page_count:
                return ParsedPageIR(page_no=page_no)
            page = doc[page_no - 1]
            raw_text = page.get_text("text") or ""

            # Text blocks
            blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            text_blocks = []
            for b in blocks:
                if b.get("type") == 0:  # text block
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            text_blocks.append(TextBlock(
                                content=span.get("text", ""),
                                bbox=(span["bbox"][0], span["bbox"][1],
                                      span["bbox"][2], span["bbox"][3]),
                                font_size=span.get("size", 0),
                                font_name=span.get("font", ""),
                                is_bold="Bold" in span.get("font", ""),
                            ))

            # Images
            images = []
            for i, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    img_data = pix.tobytes("png") if pix.n < 5 else b""
                    short_edge = min(pix.width, pix.height)
                    img_hash = hashlib.md5(img_data[:1024]).hexdigest()[:12] if img_data else ""
                    images.append(ImageInfo(
                        image_id=f"p{page_no}_img{i}",
                        data=img_data,
                        width=pix.width,
                        height=pix.height,
                        short_edge=short_edge,
                        image_hash=img_hash,
                        search_eligible=short_edge >= 200,
                    ))
                except Exception:
                    pass

            rect = page.rect
            area = max(1.0, rect.width * rect.height)
            return ParsedPageIR(
                page_no=page_no,
                text_blocks=text_blocks,
                tables=[],
                images=images,
                raw_text=raw_text,
                metadata=PageMetadata(page_width=rect.width, page_height=rect.height),
                reading_order=list(range(len(text_blocks))),
                text_coverage=len(raw_text) / area,
            )
        finally:
            doc.close()

    def _extract_pymupdf_ocr(self, path: str, page_no: int) -> ParsedPageIR:
        """最后兜底: 用 PyMuPDF 渲染后提取文字。"""
        import fitz
        doc = fitz.open(path)
        try:
            page = doc[page_no - 1]
            raw_text = page.get_text("text") or ""
            rect = page.rect
            area = max(1.0, rect.width * rect.height)
            return ParsedPageIR(
                page_no=page_no,
                text_blocks=[TextBlock(content=raw_text, bbox=(0, 0, rect.width, rect.height))],
                raw_text=raw_text,
                metadata=PageMetadata(page_width=rect.width, page_height=rect.height),
                text_coverage=len(raw_text) / area,
            )
        finally:
            doc.close()

    @staticmethod
    def _plumber_text_blocks(page) -> list[TextBlock]:
        blocks = []
        for word in (page.extract_words() or []):
            blocks.append(TextBlock(
                content=word.get("text", ""),
                bbox=(word["x0"], word["top"], word["x1"], word["bottom"]),
            ))
        return blocks

    @staticmethod
    def _plumber_tables(page) -> list[TableData]:
        tables = []
        for tbl in (page.extract_tables() or []):
            if tbl:
                rows = [[str(c or "") for c in row] for row in tbl]
                tables.append(TableData(
                    rows=rows,
                    header_row=rows[0] if rows else None,
                    column_count=len(rows[0]) if rows else 0,
                ))
        return tables

    @staticmethod
    def _plumber_images(page, path: str, page_no: int) -> list[ImageInfo]:
        images = []
        for i, img in enumerate(page.images or []):
            images.append(ImageInfo(
                image_id=f"p{page_no}_img{i}",
                bbox=(img.get("x0", 0), img.get("top", 0),
                      img.get("x1", 0), img.get("bottom", 0)),
                width=int(img.get("width", 0)),
                height=int(img.get("height", 0)),
                short_edge=min(int(img.get("width", 0)), int(img.get("height", 0))),
            ))
        return images
