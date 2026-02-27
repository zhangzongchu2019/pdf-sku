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
            if result.text_coverage > TEXT_COVERAGE_THRESHOLD or result.images:
                result.parser_backend = "pdfplumber"
                return result
        except Exception as e:
            logger.debug("pdfplumber_fallback", page=page_no, error=str(e))

        # Level 2: PyMuPDF
        try:
            result = self._extract_pymupdf(file_path, page_no)
            if result.text_coverage > TEXT_COVERAGE_THRESHOLD or result.images:
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

        # pdfplumber 不提取图片字节，用 PyMuPDF 补充
        if images:
            self._fill_image_data_pymupdf(path, page_no, images)

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
            all_img_info = page.get_images(full=True)
            # 收集所有 smask xref，这些是蒙版图层，不应作为独立图片
            smask_xrefs = set()
            for info in all_img_info:
                if len(info) > 1 and info[1] > 0:
                    smask_xrefs.add(info[1])

            img_idx = 0
            for img_info in all_img_info:
                xref = img_info[0]
                smask_xref = img_info[1] if len(img_info) > 1 else 0

                # 跳过纯蒙版图片 (它的 xref 是别人的 smask)
                if xref in smask_xrefs:
                    continue

                try:
                    pix = fitz.Pixmap(doc, xref)

                    # CMYK → RGB (在应用 mask 之前转换)
                    if pix.colorspace and pix.colorspace.n == 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    # 应用软蒙版 → 正确的透明度/裁切
                    if smask_xref > 0:
                        pix = PDFExtractor._apply_smask(fitz, doc, pix, smask_xref)

                    img_data = self._pixmap_to_png(fitz, pix)
                    if not img_data:
                        continue
                    short_edge = min(pix.width, pix.height)
                    img_hash = hashlib.md5(img_data[:1024]).hexdigest()[:12]
                    # 获取图片在页面上的位置 (PDF points)
                    img_bbox = (0, 0, 0, 0)
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            r = rects[0]
                            img_bbox = (r.x0, r.y0, r.x1, r.y1)
                    except Exception:
                        pass
                    images.append(ImageInfo(
                        image_id=f"p{page_no}_img{img_idx}",
                        bbox=img_bbox,
                        data=img_data,
                        width=pix.width,
                        height=pix.height,
                        short_edge=short_edge,
                        image_hash=img_hash,
                        search_eligible=short_edge >= 200,
                    ))
                    img_idx += 1
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
    def _pixmap_to_png(fitz, pix) -> bytes:
        """将 Pixmap 转为 PNG bytes，处理 CMYK/RGBA 等色彩空间。

        注意: pix.alpha 表示有 alpha 通道; pix.n 是 通道总数(含alpha)。
        对于带 alpha 的 PNG，不做色彩空间转换以保留透明度。
        """
        cs = pix.colorspace
        if cs is None:
            try:
                return pix.tobytes("png")
            except Exception:
                return b""
        # CMYK (cs.n == 4, 无alpha pix.n==4; 有alpha pix.n==5)
        if cs.n == 4:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        # RGB(3)/RGBA(4)/Gray(1)/GrayA(2) → PNG 原生支持
        return pix.tobytes("png")

    @staticmethod
    def _apply_smask(fitz, doc, pix, smask_xref: int):
        """给 Pixmap 应用 soft mask，返回带 alpha 的 Pixmap。"""
        try:
            mask_pix = fitz.Pixmap(doc, smask_xref)
            # mask 尺寸不匹配则跳过
            if mask_pix.width != pix.width or mask_pix.height != pix.height:
                return pix
            # 确保 mask 是灰度 (n=1, 无 alpha)
            if mask_pix.n != 1:
                mask_pix = fitz.Pixmap(fitz.csGRAY, mask_pix)
                if mask_pix.alpha:
                    # 去掉 mask 自身的 alpha
                    mask_pix = fitz.Pixmap(mask_pix, 0)  # drop alpha
            return fitz.Pixmap(pix, mask_pix)
        except Exception:
            return pix

    @staticmethod
    def _fill_image_data_pymupdf(path: str, page_no: int, images: list[ImageInfo]) -> None:
        """用 PyMuPDF 为 pdfplumber 提取的图片补充像素数据。"""
        try:
            import fitz
            doc = fitz.open(path)
            try:
                page = doc[page_no - 1]
                all_img_info = page.get_images(full=True)

                # 收集 smask xref
                smask_xrefs = set()
                for info in all_img_info:
                    if len(info) > 1 and info[1] > 0:
                        smask_xrefs.add(info[1])

                # 只处理非 mask 图片
                real_imgs = [
                    info for info in all_img_info
                    if info[0] not in smask_xrefs
                ]

                for i, img_info in enumerate(real_imgs):
                    if i >= len(images):
                        break
                    xref = img_info[0]
                    smask_xref = img_info[1] if len(img_info) > 1 else 0
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        # CMYK → RGB
                        if pix.colorspace and pix.colorspace.n == 4:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        # 应用 smask
                        if smask_xref > 0:
                            pix = PDFExtractor._apply_smask(fitz, doc, pix, smask_xref)
                        img_data = PDFExtractor._pixmap_to_png(fitz, pix)
                        if img_data:
                            images[i].data = img_data
                            images[i].width = pix.width
                            images[i].height = pix.height
                            images[i].short_edge = min(pix.width, pix.height)
                            images[i].search_eligible = images[i].short_edge >= 200
                            images[i].image_hash = hashlib.md5(img_data[:1024]).hexdigest()[:12]
                    except Exception:
                        pass
            finally:
                doc.close()
        except Exception as e:
            logger.debug("fill_image_data_failed", page=page_no, error=str(e))

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
