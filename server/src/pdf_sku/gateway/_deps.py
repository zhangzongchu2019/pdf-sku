"""
Gateway 模块依赖注入容器。
由 main.py lifespan 初始化，供 router.py 中的 get_xxx() 函数引用。
"""
from __future__ import annotations
from pdf_sku.gateway.tus_store import TusStore
from pdf_sku.gateway.tus_handler import TusHandler
from pdf_sku.gateway.file_validator import FileValidator
from pdf_sku.gateway.pdf_security import PDFSecurityChecker
from pdf_sku.gateway.prescanner import Prescanner
from pdf_sku.gateway.job_factory import JobFactory
from pdf_sku.gateway.sse_manager import SSEManager
from pdf_sku.gateway.orphan_scanner import OrphanScanner

# 这些在 lifespan 中初始化，此处先声明类型
tus_store: TusStore
tus_handler: TusHandler
job_factory: JobFactory
sse_manager: SSEManager
orphan_scanner: OrphanScanner
