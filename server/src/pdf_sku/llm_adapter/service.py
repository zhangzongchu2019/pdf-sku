"""
LLM 统一服务入口。对齐: LLM Adapter 详设 §5.2

调用链: check_budget → check_rate → check_circuit → render_prompt → client.complete → parse → record

支持:
- 加权轮询: 每个 provider 按并发权重重复出现在 robin pool 中
- 连续超时自动跳过: 连续 N 次超时后自动禁用 provider (下次重启恢复)
"""
from __future__ import annotations
import asyncio
import itertools
import os
import time
from pdf_sku.llm_adapter.client.base import BaseLLMClient, LLMResponse
from pdf_sku.llm_adapter.client.registry import get_client
from pdf_sku.llm_adapter.prompt.engine import PromptEngine
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser, ParseResult
from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
from pdf_sku.llm_adapter.resilience.budget_guard import BudgetGuard
from pdf_sku.llm_adapter.resilience.rate_limiter import RateLimiter
from pdf_sku.evaluator.scorer import PageScore
from pdf_sku.common.exceptions import LLMCircuitOpenError, RetryableError
import structlog

logger = structlog.get_logger()

MAX_RETRIES_PER_PROVIDER = 3  # 每个 provider 的重试次数
EVAL_BATCH_SIZE = 5
# 全局 LLM 并发上限，防止 API 429。通过环境变量 LLM_MAX_CONCURRENCY 可调。
LLM_MAX_CONCURRENCY = int(os.environ.get("LLM_MAX_CONCURRENCY", "120"))
# 连续超时阈值: 连续 N 次超时后自动禁用 provider
CONSECUTIVE_ERROR_LIMIT = int(os.environ.get("LLM_ERROR_SKIP_THRESHOLD", "3"))
PROVIDER_COOLDOWN_SECONDS = int(os.environ.get("LLM_PROVIDER_COOLDOWN", "600"))  # 10 minutes
# 默认请求超时 (秒): 通过环境变量 LLM_TIMEOUT_SECONDS 覆盖
DEFAULT_TIMEOUT = float(os.environ.get("LLM_TIMEOUT_SECONDS", "300"))  # 5 minutes
# 连续超时致命阈值: 连续 N 次超时后程序退出
CONSECUTIVE_TIMEOUT_FATAL = int(os.environ.get("LLM_CONSECUTIVE_TIMEOUT_FATAL", "3"))


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
        fallback_chain: list[str] | None = None,
        provider_weights: dict[str, int] | None = None,
    ) -> None:
        self._prompt = prompt_engine
        self._parser = parser
        self._circuit = circuit_breaker
        self._budget = budget_guard
        self._rate_limiter = rate_limiter
        self._default_client = default_client_name
        self._fallback_chain = fallback_chain or []
        self._llm_semaphore = asyncio.Semaphore(LLM_MAX_CONCURRENCY)

        # 加权轮询: 按并发权重重复 provider 名称
        # provider_weights: {"openrouter": 4, "openrouter_1": 4, "openrouter_nebula": 2, ...}
        weights = provider_weights or {}
        pool_entries: list[str] = []
        pool_members = [
            n for n in self._fallback_chain if weights.get(n, 0) > 0
        ] or [default_client_name]
        for name in pool_members:
            w = weights.get(name, 1)
            pool_entries.extend([name] * w)
        self._robin_pool = pool_entries if pool_entries else [default_client_name]
        self._robin_iter = itertools.cycle(self._robin_pool)

        # 连续错误计数器 (per provider)
        self._consecutive_errors: dict[str, int] = {}
        self._disabled_until: dict[str, float] = {}  # provider → timestamp when re-enabled
        # 全局连续超时计数 (跨 provider)
        self._consecutive_timeouts_global: int = 0

    @property
    def current_model_name(self) -> str:
        try:
            return get_client(self._default_client).model_id
        except KeyError:
            return self._default_client

    def _is_provider_disabled(self, name: str) -> bool:
        if name not in self._disabled_until:
            return False
        import time
        if time.monotonic() >= self._disabled_until[name]:
            # 冷却结束，重新启用
            del self._disabled_until[name]
            self._consecutive_errors[name] = 0
            logger.info("provider_auto_reenabled", provider=name)
            return False
        return True

    def _record_error(self, name: str) -> None:
        """记录错误，连续达到阈值时自动禁用 5 分钟。"""
        self._consecutive_errors[name] = self._consecutive_errors.get(name, 0) + 1
        count = self._consecutive_errors[name]
        if count >= CONSECUTIVE_ERROR_LIMIT:
            import time
            self._disabled_until[name] = time.monotonic() + PROVIDER_COOLDOWN_SECONDS
            logger.warning("provider_auto_disabled",
                           provider=name, consecutive_errors=count,
                           cooldown_seconds=PROVIDER_COOLDOWN_SECONDS)

    def _record_success(self, name: str) -> None:
        """成功后重置错误计数。"""
        if name in self._consecutive_errors:
            self._consecutive_errors[name] = 0

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

    async def _call_llm(
        self,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        client_name: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> LLMResponse:
        """
        核心调用链: semaphore → circuit → rate_limit → budget → client.complete → record。
        带重试 + Provider Fallback 链。
        """
        async with self._llm_semaphore:
            return await self._call_llm_inner(
                operation, prompt, images, client_name, timeout)

    async def _call_llm_inner(
        self,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        client_name: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> LLMResponse:
        """实际 LLM 调用（已在 Semaphore 内）。"""
        # 轮询选择 primary: 跳过已禁用的 provider
        if client_name:
            primary = client_name
        elif len(self._robin_pool) > 1:
            # 最多尝试 pool 长度次，跳过已禁用的
            for _ in range(len(self._robin_pool)):
                candidate = next(self._robin_iter)
                if not self._is_provider_disabled(candidate):
                    primary = candidate
                    break
            else:
                # 全部禁用 → 用第一个（强制重试）
                primary = self._robin_pool[0]
        else:
            primary = self._default_client

        # 构建尝试顺序: primary → fallback chain 中的其他 provider (跳过已禁用的)
        providers = [primary]
        for fb in self._fallback_chain:
            if fb != primary and fb not in providers and not self._is_provider_disabled(fb):
                providers.append(fb)

        # 总重试次数: provider数量 * 每provider重试次数 - 1
        # 确保充分利用所有可用 provider
        max_total_attempts = len(providers) * MAX_RETRIES_PER_PROVIDER - 1
        total_attempts = 0
        last_error = None

        for provider_name in providers:
            client = get_client(provider_name)
            if not client:
                continue

            for attempt in range(MAX_RETRIES_PER_PROVIDER):
                if total_attempts >= max_total_attempts:
                    break

                # 1. 熔断检查
                try:
                    self._circuit.check()
                except LLMCircuitOpenError:
                    if provider_name == providers[-1]:
                        raise
                    break  # 跳到下一个 provider

                # 2. 限流检查
                if self._rate_limiter:
                    await self._rate_limiter.check_and_acquire()

                # 3. 预算检查
                if self._budget:
                    await self._budget.check(operation)

                try:
                    resp = await asyncio.wait_for(
                        client.complete(
                            prompt=prompt,
                            images=images,
                            json_mode=True,
                        ),
                        timeout=timeout,
                    )

                    # 成功 → 重置连续超时计数
                    self._circuit.record_success()
                    self._record_success(provider_name)
                    self._consecutive_timeouts_global = 0

                    # 记录消耗
                    input_tokens = resp.usage.get("input_tokens", 0)
                    output_tokens = resp.usage.get("output_tokens", 0)

                    if self._budget:
                        cost = self._estimate_cost(client.provider, input_tokens, output_tokens)
                        await self._budget.record_usage(cost)

                    if self._rate_limiter:
                        await self._rate_limiter.record_tokens(
                            input_tokens + output_tokens)

                    if provider_name != primary:
                        logger.info("llm_fallback_success",
                                    provider=provider_name, operation=operation)

                    return resp

                except asyncio.TimeoutError:
                    self._circuit.record_failure()
                    last_error = TimeoutError(f"LLM request timed out after {timeout}s")
                    total_attempts += 1
                    self._consecutive_timeouts_global = getattr(
                        self, '_consecutive_timeouts_global', 0) + 1
                    logger.warning("llm_request_timeout",
                                    timeout=timeout, attempt=attempt + 1,
                                    operation=operation, provider=provider_name,
                                    consecutive=self._consecutive_timeouts_global)
                    # 连续超时达到致命阈值 → 抛出致命异常终止程序
                    if self._consecutive_timeouts_global >= CONSECUTIVE_TIMEOUT_FATAL:
                        msg = (f"连续 {self._consecutive_timeouts_global} 次请求超时，"
                               f"程序退出。请检查 LLM 服务可用性。")
                        logger.error("llm_consecutive_timeout_fatal", message=msg)
                        raise SystemExit(msg)
                    if attempt < MAX_RETRIES_PER_PROVIDER - 1:
                        continue
                    self._record_error(provider_name)
                    break

                except Exception as e:
                    self._circuit.record_failure()
                    last_error = e
                    total_attempts += 1
                    # 非超时错误重置连续超时计数
                    self._consecutive_timeouts_global = 0

                    if attempt < MAX_RETRIES_PER_PROVIDER - 1:
                        logger.warning("llm_call_retry",
                                        attempt=attempt + 1, error=repr(e),
                                        operation=operation,
                                        provider=provider_name)
                        continue
                    # 本 provider 重试耗尽，记录一次连续错误
                    self._record_error(provider_name)
                    logger.warning("llm_provider_exhausted",
                                    provider=provider_name, error=repr(e),
                                    operation=operation)
                    break

        raise RetryableError(
            f"LLM call failed after {total_attempts} attempts "
            f"across {len(providers)} providers: {last_error}"
        )

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


def _is_timeout_error(e: Exception) -> bool:
    """判断异常是否为超时/连接错误。"""
    import httpx
    if isinstance(e, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout,
                       httpx.ConnectError, asyncio.TimeoutError, TimeoutError,
                       ConnectionError)):
        return True
    err_str = str(e).lower()
    return any(k in err_str for k in ("timeout", "timed out", "connection"))
