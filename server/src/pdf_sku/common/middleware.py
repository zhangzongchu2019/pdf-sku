"""全局错误处理中间件。"""
from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pdf_sku.common.exceptions import PDFSKUError
import structlog

logger = structlog.get_logger()


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PDFSKUError)
    async def handle_pdfsku_error(request: Request, exc: PDFSKUError):
        logger.warning("business_error",
                       code=exc.code, message=str(exc),
                       status=getattr(exc, "http_status", 400))
        return JSONResponse(
            status_code=getattr(exc, "http_status", 400),
            content={
                "error_code": exc.code,
                "message": str(exc),
                "severity": getattr(exc, "severity", "error"),
            },
        )

    @app.exception_handler(FileNotFoundError)
    async def handle_not_found(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content={
            "error_code": "NOT_FOUND", "message": str(exc)})

    @app.exception_handler(Exception)
    async def handle_general_error(request: Request, exc: Exception):
        logger.exception("unhandled_error", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error_code": "INTERNAL_ERROR", "message": "Internal server error"},
        )
