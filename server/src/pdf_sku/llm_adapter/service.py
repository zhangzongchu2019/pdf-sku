"""
LLM 统一服务入口。对齐: LLM Adapter 详设 §5.2

调用链: check_budget → check_rate → check_circuit → render_prompt → client.complete → parse → record
"""
from __future__ import annotations
import asyncio
import time
from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse
from pdf_sku.llm_adapter.client.registry import get_client
from pdf_sku.llm_adapter.prompt.engine import PromptEngine
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser, ParseResult
from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
from pdf_sku.llm_adapter.resilience.budget_guard import BudgetGuard
from pdf_sku.llm_adapter.resilience.rate_limiter import RateLimiter
from pdf_sku.evaluator.scorer import PageScore
from pdf_sku.llm_adapter.provider_config import get_provider_config, get_provider_entries
from pdf_sku.common.exceptions import LLMCircuitOpenError, RetryableError
import structlog

logger = structlog.get_logger()

EVAL_BATCH_SIZE = 3


class LLMService:
    """
    LLM 统一调用服务。所有 LLM 调用都通过此入口。

    集成: 熔断 → 限流 → 预算 → Prompt → Client → Parse → 记录
    """

    def __init__(
        self,
        prompt_engine: PromptEngine,
        parser: ResponseParser,
        circuit_breaker: CircuitBreaker,
        budget_guard: BudgetGuard | None = None,
        rate_limiter: RateLimiter | None = None,
        default_client_name: str = "gemini",
        redis=None,
    ) -> None:
        self._prompt = prompt_engine
        self._parser = parser
        self._circuit = circuit_breaker
        self._budget = budget_guard
        self._rate_limiter = rate_limiter
        self._default_client = default_client_name
        self._redis = redis
        self._last_used_provider: str | None = None

    @property
    def current_model_name(self) -> str:
        name = self._last_used_provider or self._default_client
        try:
            client = get_client(name)
            return client.model_id if client else name
        except (KeyError, AttributeError):
            return name

    async def evaluate_document(
        self,
        screenshots: list[bytes],
        category: str | None = None,
        sample_pages: list[int] | None = None,
    ) -> list[PageScore]:
        """
        文档级评估: 多页截图 → LLM → PageScore list。

        对齐: Evaluator 详设 §5.1 Step 4
        """
        prompt_text = self._prompt.get_prompt("eval_document", {
            "category": category or "",
        })

        pages = sample_pages or list(range(1, len(screenshots) + 1))
        page_scores: list[PageScore] = []

        # 分批发送图片，每批最多 EVAL_BATCH_SIZE 张
        for batch_start in range(0, len(screenshots), EVAL_BATCH_SIZE):
            batch_end = batch_start + EVAL_BATCH_SIZE
            batch_images = screenshots[batch_start:batch_end]
            batch_pages = pages[batch_start:batch_end]

            logger.info("eval_document_batch",
                        batch_start=batch_start,
                        batch_size=len(batch_images),
                        total=len(screenshots))

            llm_response = await self._call_llm(
                operation="evaluate_document",
                prompt=prompt_text,
                images=batch_images,
            )

            # 解析响应
            raw_scores = self._parser.parse_eval_scores(llm_response.content)

            for i, score_data in enumerate(raw_scores):
                page_no = batch_pages[i] if i < len(batch_pages) else batch_start + i + 1
                if isinstance(score_data, dict):
                    ps = PageScore(
                        page_no=page_no,
                        overall=float(score_data.get("overall", 0.5)),
                        dimensions={
                            "text_clarity": float(score_data.get("text_clarity", 0.5)),
                            "image_quality": float(score_data.get("image_quality", 0.5)),
                            "layout_structure": float(score_data.get("layout_structure", 0.5)),
                            "table_regularity": float(score_data.get("table_regularity", 0.5)),
                            "sku_density": float(score_data.get("sku_density", 0.5)),
                        },
                        raw_response=str(score_data),
                    )
                else:
                    ps = PageScore(page_no=page_no, overall=0.5)
                page_scores.append(ps)

            logger.info("eval_document_batch_done",
                        batch_start=batch_start,
                        batch_scores=len(raw_scores),
                        model=llm_response.model,
                        tokens_in=llm_response.usage.get("input_tokens", 0),
                        tokens_out=llm_response.usage.get("output_tokens", 0),
                        latency_ms=llm_response.latency_ms)

        logger.info("eval_document_complete",
                     pages=len(page_scores),
                     avg_overall=round(sum(p.overall for p in page_scores) / max(len(page_scores), 1), 3))

        return page_scores

    async def evaluate_page_lightweight(
        self,
        screenshot: bytes,
        model_override: str | None = None,
    ) -> float:
        """单页轻量评估 → score float。"""
        prompt = self._prompt.get_prompt("eval_page_lightweight")
        client_name = model_override or "qwen"

        try:
            resp = await self._call_llm(
                operation="evaluate_page",
                prompt=prompt,
                images=[screenshot],
                client_name=client_name,
                timeout=30.0,
            )
            return self._parser.parse_page_score(resp.content)
        except Exception as e:
            logger.warning("lightweight_eval_failed", error=str(e))
            return 0.5

    async def call_llm(
        self,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        client_name: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Public interface for _call_llm. Use this from external callers."""
        return await self._call_llm(
            operation=operation, prompt=prompt, images=images,
            client_name=client_name, timeout=timeout,
        )

    async def _call_llm(
        self,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        client_name: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """
        核心调用链: circuit → rate_limit → budget → client.complete → record。
        带重试 + fallback 到下一个 enabled provider。
        """
        # Build ordered list of providers to try
        providers_to_try = await self._build_fallback_chain(client_name)

        last_error: Exception | None = None
        for provider_name in providers_to_try:
            try:
                resp = await self._call_single_provider(
                    provider_name, operation, prompt, images, timeout,
                )
                self._last_used_provider = provider_name
                return resp
            except LLMCircuitOpenError:
                raise  # 不 fallback
            except Exception as e:
                last_error = e
                logger.warning("llm_provider_failed",
                               provider=provider_name, operation=operation,
                               error=repr(e))
                continue

        raise RetryableError(
            f"All LLM providers failed for '{operation}': {last_error}")

    async def _build_fallback_chain(self, client_name: str | None) -> list[str]:
        """Build ordered list of enabled provider names to try.

        优先级来源: Redis provider entries (用户可在前端调整顺序)。
        若指定了 client_name 则将其提到最前，其余按 Redis 顺序追加。
        """
        # Get enabled providers from Redis (source of truth for priority & enabled)
        entries: list | None = None
        try:
            entries = await get_provider_entries(self._redis)
        except Exception:
            pass  # Redis unavailable — skip filtering

        if entries:
            # 按 Redis 优先级构建链（已按 priority 排序）
            chain: list[str] = []
            if client_name:
                # 指定的 client 优先
                chain.append(client_name)
            for entry in entries:
                if entry.enabled and entry.name not in chain:
                    chain.append(entry.name)
        else:
            # Redis 不可用，回退到 default
            chain = [client_name or self._default_client]

        # Fallback: if everything is disabled, use the default client anyway
        if not chain:
            chain = [client_name or self._default_client]

        return chain

    async def _call_single_provider(
        self,
        client_name: str,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Call a single provider with retries."""
        client = get_client(client_name)

        # Dynamic per-provider config from Redis (with code defaults fallback)
        provider_cfg = await get_provider_config(self._redis, client.provider)
        max_retries = provider_cfg.max_retries

        for attempt in range(max_retries + 1):
            # 1. 熔断检查
            self._circuit.check()

            # 2. 限流检查 (per-provider)
            if self._rate_limiter:
                await self._rate_limiter.check_and_acquire(provider_name=client_name)

            # 3. 预算检查
            if self._budget:
                await self._budget.check(operation)

            try:
                # Determine effective timeout
                if timeout is not None:
                    effective_timeout = timeout
                elif images:
                    effective_timeout = float(provider_cfg.vlm_timeout_seconds)
                else:
                    effective_timeout = float(provider_cfg.timeout_seconds)

                resp = await client.complete(
                    prompt=prompt,
                    images=images,
                    json_mode=True,
                    timeout=effective_timeout,
                )

                # 成功
                self._circuit.record_success()

                # 记录消耗
                input_tokens = resp.usage.get("input_tokens", 0)
                output_tokens = resp.usage.get("output_tokens", 0)

                if self._budget:
                    cost = self._estimate_cost(client.provider, input_tokens, output_tokens)
                    await self._budget.record_usage(cost)

                if self._rate_limiter:
                    await self._rate_limiter.record_tokens(
                        input_tokens + output_tokens, provider_name=client_name)

                return resp

            except LLMCircuitOpenError:
                raise  # 不重试
            except Exception as e:
                self._circuit.record_failure()
                if attempt < max_retries:
                    backoff = 2 ** attempt * 3  # 3s, 6s
                    logger.warning("llm_call_retry",
                                    attempt=attempt + 1, error=repr(e),
                                    operation=operation, backoff_s=backoff,
                                    provider=client_name)
                    await asyncio.sleep(backoff)
                    continue
                raise RetryableError(
                    f"LLM call to {client_name} failed after {max_retries + 1} attempts: {e}")

        raise RetryableError(f"LLM call to {client_name} exhausted all retries")

    @staticmethod
    def _estimate_cost(provider: str, input_tokens: int, output_tokens: int) -> float:
        """估算 LLM 调用成本 (USD)。"""
        # Pricing per 1M tokens (approximate)
        pricing = {
            "gemini": {"input": 0.075, "output": 0.30},   # Flash
            "qwen":   {"input": 0.004, "output": 0.012},  # qwen-max
        }
        rates = pricing.get(provider, {"input": 0.10, "output": 0.30})
        return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
