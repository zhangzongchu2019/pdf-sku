"""
响应解析器 (4 级 fallback)。对齐: LLM Adapter 详设 §5

Level 1: 直接 JSON parse
Level 2: 提取 markdown code block 内的 JSON
Level 3: 正则提取 JSON 结构
Level 4: 返回 raw text (调用方自行处理)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any
import orjson
import structlog

logger = structlog.get_logger()


@dataclass
class ParseResult:
    success: bool = False
    data: Any = None
    raw_text: str = ""
    parse_level: int = 0
    error: str | None = None


class ResponseParser:
    def parse(self, text: str, expected_type: str = "auto") -> ParseResult:
        """
        解析 LLM 响应文本 → 结构化数据。

        Args:
            text: LLM 原始响应
            expected_type: "array" | "object" | "auto"
        """
        if not text or not text.strip():
            return ParseResult(raw_text=text, error="empty_response")

        # Level 1: 直接 JSON parse
        result = self._try_direct_json(text)
        if result.success:
            result.parse_level = 1
            return result

        # Level 2: Markdown code block
        result = self._try_code_block(text)
        if result.success:
            result.parse_level = 2
            return result

        # Level 3: 正则提取
        result = self._try_regex_extract(text, expected_type)
        if result.success:
            result.parse_level = 3
            return result

        # Level 4: Raw text fallback
        logger.warning("parse_fallback_raw", text_preview=text[:200])
        return ParseResult(
            success=False, data=None, raw_text=text,
            parse_level=4, error="all_parse_methods_failed",
        )

    def _try_direct_json(self, text: str) -> ParseResult:
        try:
            data = orjson.loads(text.strip())
            return ParseResult(success=True, data=data, raw_text=text)
        except Exception:
            return ParseResult(raw_text=text)

    def _try_code_block(self, text: str) -> ParseResult:
        """提取 ```json ... ``` 或 ``` ... ``` 内容。"""
        patterns = [
            r'```json\s*\n?(.*?)\n?\s*```',
            r'```\s*\n?(.*?)\n?\s*```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    data = orjson.loads(match.group(1).strip())
                    return ParseResult(success=True, data=data, raw_text=text)
                except Exception:
                    continue
        return ParseResult(raw_text=text)

    def _try_regex_extract(self, text: str, expected_type: str) -> ParseResult:
        """尝试正则提取 JSON 数组或对象。"""
        if expected_type in ("array", "auto"):
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    data = orjson.loads(match.group(0))
                    return ParseResult(success=True, data=data, raw_text=text)
                except Exception:
                    pass

        if expected_type in ("object", "auto"):
            match = re.search(r'\{[\s\S]*\}', text)
            if match:
                try:
                    data = orjson.loads(match.group(0))
                    return ParseResult(success=True, data=data, raw_text=text)
                except Exception:
                    pass

        return ParseResult(raw_text=text)

    def parse_eval_scores(self, text: str) -> list[dict]:
        """专用: 解析 evaluate_document 响应 → PageScore list。"""
        result = self.parse(text, expected_type="array")
        if result.success and isinstance(result.data, list):
            return result.data

        # 单页响应可能是 object
        result = self.parse(text, expected_type="object")
        if result.success and isinstance(result.data, dict):
            return [result.data]

        logger.error("eval_score_parse_failed", text_preview=text[:200])
        return []

    def parse_page_score(self, text: str) -> float:
        """专用: 解析 lightweight eval 响应 → score float。"""
        result = self.parse(text, expected_type="object")
        if result.success and isinstance(result.data, dict):
            return float(result.data.get("score", 0.5))
        return 0.5  # 中性分
