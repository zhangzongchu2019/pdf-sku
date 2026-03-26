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
    db_pool_timeout: int = 30
    db_pool_pre_ping: bool = True
    sql_echo: bool = False

    @property
    def database_pool_size(self) -> int:
        return self.db_pool_size

    @property
    def database_max_overflow(self) -> int:
        return self.db_max_overflow

    @property
    def database_pool_timeout(self) -> int:
        return self.db_pool_timeout

    @property
    def database_pool_pre_ping(self) -> bool:
        return self.db_pool_pre_ping

    # === Workload control ===
    process_pool_workers: int = max(2, min(4, os.cpu_count() or 2))
    evaluation_job_concurrency: int = 2
    evaluation_queue_size: int = 100
    pipeline_job_concurrency: int = 2
    pipeline_queue_size: int = 100
    pipeline_page_concurrency: int = 3
    global_page_concurrency: int = 8
    output_job_concurrency: int = 2
    output_queue_size: int = 200

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
    gemini_api_base: str = "https://generativelanguage.googleapis.com"
    gemini_model: str = "gemini-2.0-flash"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-vl-max"
    openrouter_api_key: str = ""
    openrouter_api_keys: str = ""  # 多 key 轮询: 逗号分隔 "key1,key2,key3"
    openrouter_api_base: str = "https://openrouter.ai/api"
    openrouter_model: str = "google/gemini-2.5-flash"
    apiyi_api_key: str = ""
    apiyi_api_base: str = "https://api.apiyi.com"
    apiyi_model: str = "gemini-2.5-flash"
    nebula_api_key: str = ""
    nebula_api_base: str = "https://llm.ai-nebula.com"
    nebula_model: str = "gemini-2.5-flash-nothinking"
    wanjie_api_key: str = ""
    wanjie_api_base: str = "https://maas-openapi.wanjiedata.com/api"
    wanjie_model: str = "gemini-2.5-flash"
    gptproto_api_key: str = ""
    gptproto_api_base: str = "https://gptproto.com"
    gptproto_model: str = "gemini-2.5-flash"
    default_llm_client: str = ""
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
    benchmark_image_dir: str = "/data/benchmark_images"

    # === Layout Detection & OCR ===
    local_model_device: str = "auto"  # auto | cpu | cuda | cuda:N | mps
    layout_detect_enabled: bool = True
    doclayout_model_path: str = ""
    layout_detect_confidence: float = 0.25
    ocr_enabled: bool = True
    ocr_dpi: int = 200
    ocr_min_text_length: int = 50  # 低于此阈值不启用 OCR-guided (20→50, 避免短文本噪音)

    # === Combo Catalog Detection ===
    combo_detect_enabled: bool = True
    combo_keyword_page_ratio: float = 0.3
    combo_multi_category_page_ratio: float = 0.5
    combo_max_avg_sku_per_page: float = 3.0

    # === Limits ===
    max_upload_size_mb: int = 16384
    max_page_count: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
