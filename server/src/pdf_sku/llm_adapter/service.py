"""
LLM 统一服务入口。对齐: LLM Adapter 详设 §5.2

调用链: check_budget → check_rate → check_circuit → render_prompt → client.complete → parse → record
"""
from __future__ import annotations
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

MAX_RETRIES = 2


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
    ) -> None:
        self._prompt = prompt_engine
        self._parser = parser
        self._circuit = circuit_breaker
        self._budget = budget_guard
        self._rate_limiter = rate_limiter
        self._default_client = default_client_name

    @property
    def current_model_name(self) -> str:
        try:
            return get_client(self._default_client).model_name
        except KeyError:
            return self._default_client

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

        llm_response = await self._call_llm(
            operation="evaluate_document",
            prompt=prompt_text,
            images=screenshots,
        )

        # 解析响应
        raw_scores = self._parser.parse_eval_scores(llm_response.text)

        # 转换为 PageScore
        pages = sample_pages or list(range(1, len(raw_scores) + 1))
        page_scores: list[PageScore] = []

        for i, score_data in enumerate(raw_scores):
            page_no = pages[i] if i < len(pages) else i + 1
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

        logger.info("eval_document_complete",
                     pages=len(page_scores),
                     avg_overall=round(sum(p.overall for p in page_scores) / max(len(page_scores), 1), 3),
                     model=llm_response.model,
                     tokens_in=llm_response.input_tokens,
                     tokens_out=llm_response.output_tokens,
                     latency_ms=llm_response.latency_ms)

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
            return self._parser.parse_page_score(resp.text)
        except Exception as e:
            logger.warning("lightweight_eval_failed", error=str(e))
            return 0.5

    async def _call_llm(
        self,
        operation: str,
        prompt: str,
        images: list[bytes] | None = None,
        client_name: str | None = None,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """
        核心调用链: circuit → rate_limit → budget → client.complete → record。
        带重试 (最多 MAX_RETRIES 次)。
        """
        client_name = client_name or self._default_client

        for attempt in range(MAX_RETRIES + 1):
            # 1. 熔断检查
            self._circuit.check()

            # 2. 限流检查
            if self._rate_limiter:
                await self._rate_limiter.check_and_acquire()

            # 3. 预算检查
            if self._budget:
                await self._budget.check(operation)

            try:
                client = get_client(client_name)

                resp = await client.complete(
                    prompt=prompt,
                    images=images,
                    json_mode=True,
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
                        input_tokens + output_tokens)

                return resp

            except LLMCircuitOpenError:
                raise  # 不重试
            except Exception as e:
                self._circuit.record_failure()
                if attempt < MAX_RETRIES:
                    logger.warning("llm_call_retry",
                                    attempt=attempt + 1, error=str(e),
                                    operation=operation)
                    continue
                raise RetryableError(f"LLM call failed after {MAX_RETRIES + 1} attempts: {e}")

        raise RetryableError("LLM call exhausted all retries")

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
