from unittest.mock import AsyncMock

import pytest

from pdf_sku.llm_adapter.client.base import LLMResponse
from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
from pdf_sku.llm_adapter.service import LLMService


class DummyPromptEngine:
    def get_prompt(self, _name, _context=None):
        return "prompt"


class DummyParser:
    def parse_eval_scores(self, _text: str):
        return [{
            "overall": None,
            "text_clarity": None,
            "image_quality": "0.8",
            "layout_structure": "",
            "table_regularity": "bad",
            "sku_density": 0.9,
        }]


@pytest.mark.asyncio
async def test_evaluate_document_tolerates_null_score_fields():
    service = LLMService(
        prompt_engine=DummyPromptEngine(),
        parser=DummyParser(),
        circuit_breaker=CircuitBreaker(),
        redis=None,
    )
    service._call_llm = AsyncMock(
        return_value=LLMResponse(
            content="[]",
            model="gemini-test",
            usage={"input_tokens": 1, "output_tokens": 1},
            latency_ms=10,
        )
    )

    scores = await service.evaluate_document([b"img"], sample_pages=[3])

    assert len(scores) == 1
    assert scores[0].page_no == 3
    assert scores[0].overall == 0.5
    assert scores[0].dimensions == {
        "text_clarity": 0.5,
        "image_quality": 0.8,
        "layout_structure": 0.5,
        "table_regularity": 0.5,
        "sku_density": 0.9,
    }
