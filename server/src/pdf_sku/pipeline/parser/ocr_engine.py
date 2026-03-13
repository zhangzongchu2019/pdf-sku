"""
OCR 引擎 — 基于 RapidOCR (PaddleOCR ONNX 轻量封装)。

将页面高清截图 (DPI 300) 输入 RapidOCR，输出结构化文字块列表。
懒加载单例，线程安全。
"""
from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

import structlog


_nvidia_preloaded = False

def _ensure_nvidia_libs() -> None:
    """预加载 pip 安装的 nvidia CUDA 库 (必须在 import onnxruntime 之前)。"""
    global _nvidia_preloaded
    if _nvidia_preloaded:
        return
    _nvidia_preloaded = True

    site_packages = Path(sys.prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages" / "nvidia"
    if not site_packages.exists():
        return

    # 按依赖顺序预加载关键 so 文件
    import ctypes
    load_order = [
        "cuda_runtime/lib/libcudart.so.12",
        "cublas/lib/libcublasLt.so.12",
        "cublas/lib/libcublas.so.12",
        "curand/lib/libcurand.so.10",
        "cufft/lib/libcufft.so.11",
        "cudnn/lib/libcudnn.so.9",
    ]
    for rel in load_order:
        so_path = site_packages / rel
        if so_path.exists():
            try:
                ctypes.CDLL(str(so_path), mode=ctypes.RTLD_GLOBAL)
            except OSError:
                pass

logger = structlog.get_logger()


@dataclass
class OcrBlock:
    """单个 OCR 识别文字块。"""
    text: str
    bbox: tuple[float, float, float, float]  # x0, y0, x1, y1 (像素坐标)
    confidence: float


class _OcrHolder:
    """懒加载单例，进程内只初始化一次 RapidOCR。"""

    _instance: _OcrHolder | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.engine = None
        self.available = False
        self._loaded = False

    @classmethod
    def get(cls) -> _OcrHolder:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            _ensure_nvidia_libs()
            try:
                from rapidocr_onnxruntime import RapidOCR
                # 尝试 GPU 加速，失败则回退 CPU
                try:
                    self.engine = RapidOCR(
                        det_use_cuda=True,
                        rec_use_cuda=True,
                        cls_use_cuda=True,
                    )
                    self.available = True
                    logger.info("ocr_engine_loaded", backend="rapidocr_onnxruntime", gpu=True)
                except Exception:
                    self.engine = RapidOCR()
                    self.available = True
                    logger.info("ocr_engine_loaded", backend="rapidocr_onnxruntime", gpu=False)
            except ImportError:
                logger.warning("ocr_engine_skip", reason="rapidocr-onnxruntime not installed")
            except Exception as exc:
                logger.warning("ocr_engine_load_failed", error=str(exc))


class OcrEngine:
    """OCR 引擎封装。"""

    def run(self, image_bytes: bytes) -> list[OcrBlock]:
        """对页面截图执行 OCR，返回文字块列表。

        Args:
            image_bytes: PNG 格式的页面截图 (建议 DPI 300)

        Returns:
            OcrBlock 列表，每个包含 text, bbox(像素), confidence
        """
        holder = _OcrHolder.get()
        holder.load()
        if not holder.available or not holder.engine:
            return []

        try:
            result, _ = holder.engine(image_bytes)
            if not result:
                return []

            blocks: list[OcrBlock] = []
            for item in result:
                # RapidOCR 返回: [[x0,y0],[x1,y1],[x2,y2],[x3,y3]], text, confidence
                points, text, conf = item
                if not text or not text.strip():
                    continue
                # 取四点的外接矩形
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                bbox = (min(xs), min(ys), max(xs), max(ys))
                blocks.append(OcrBlock(
                    text=text.strip(),
                    bbox=bbox,
                    confidence=float(conf),
                ))
            return blocks

        except Exception as exc:
            logger.warning("ocr_run_failed", error=str(exc))
            return []

    @staticmethod
    def blocks_to_text(blocks: list[OcrBlock]) -> str:
        """将 OCR 块按垂直位置排序后拼接为纯文本。"""
        if not blocks:
            return ""
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        return "\n".join(b.text for b in sorted_blocks)

    @staticmethod
    def total_text_length(blocks: list[OcrBlock]) -> int:
        """OCR 块总文本长度。"""
        return sum(len(b.text) for b in blocks)
