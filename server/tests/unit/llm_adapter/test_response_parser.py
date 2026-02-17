"""ResponseParser 单元测试。"""
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser


def test_direct_json():
    p = ResponseParser()
    result = p.parse('[{"score": 0.85}]')
    assert result.success
    assert result.parse_level == 1
    assert result.data[0]["score"] == 0.85


def test_code_block_json():
    p = ResponseParser()
    text = 'Here is the result:\n```json\n{"score": 0.9}\n```'
    result = p.parse(text)
    assert result.success
    assert result.parse_level == 2
    assert result.data["score"] == 0.9


def test_regex_extract_array():
    p = ResponseParser()
    text = 'The scores are: [{"a": 1}, {"a": 2}] and that is all.'
    result = p.parse(text, expected_type="array")
    assert result.success
    assert result.parse_level == 3
    assert len(result.data) == 2


def test_regex_extract_object():
    p = ResponseParser()
    text = 'Result: {"page_type": "product_listing", "confidence": 0.92}'
    result = p.parse(text, expected_type="object")
    assert result.success
    assert result.data["page_type"] == "product_listing"


def test_fallback_raw():
    p = ResponseParser()
    result = p.parse("This is not JSON at all")
    assert not result.success
    assert result.parse_level == 4
    assert result.raw_text == "This is not JSON at all"


def test_empty_input():
    p = ResponseParser()
    result = p.parse("")
    assert not result.success
    assert result.error == "empty_response"


def test_parse_eval_scores():
    p = ResponseParser()
    text = '[{"page_no": 1, "overall": 0.85, "text_clarity": 0.9}]'
    scores = p.parse_eval_scores(text)
    assert len(scores) == 1
    assert scores[0]["overall"] == 0.85


def test_parse_page_score():
    p = ResponseParser()
    text = '{"score": 0.72, "reason": "Good layout"}'
    score = p.parse_page_score(text)
    assert score == 0.72


def test_parse_page_score_fallback():
    p = ResponseParser()
    score = p.parse_page_score("invalid")
    assert score == 0.5  # 中性分
