"""应用配置。所有环境变量集中管理。"""
from __future__ import annotations
import os
import socket
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === App ===
    app_env: str = "development"
    app_title: str = "PDF-SKU Server"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    worker_id: str = os.environ.get("WORKER_ID", f"worker-{socket.gethostname()}")
    log_level: str = "INFO"

    # === Database ===
    database_url: str = "postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    sql_echo: bool = False

    @property
    def database_pool_size(self) -> int:
        return self.db_pool_size

    @property
    def database_max_overflow(self) -> int:
        return self.db_max_overflow

    # === Redis ===
    redis_url: str = "redis://localhost:6379/0"
    redis_sentinel_hosts: str = ""
    redis_sentinel_master: str = "mymaster"

    # === MinIO ===
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "pdf-sku"
    minio_secure: bool = False

    # === LLM ===
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-vl-max"
    llm_daily_budget_usd: float = 50.0
    llm_timeout_seconds: int = 60

    # === Collaboration ===
    wecom_webhook_url: str = ""
    dingtalk_webhook_url: str = ""

    # === Output ===
    downstream_import_url: str = ""
    downstream_check_url: str = ""

    # === Langfuse ===
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # === Paths ===
    tus_upload_dir: str = "/data/tus-uploads"
    job_data_dir: str = "/data/jobs"

    # === Limits ===
    max_upload_size_mb: int = 16384
    max_page_count: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
