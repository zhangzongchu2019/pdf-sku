"""AttrPromotionChecker 测试。"""
from pdf_sku.feedback.promotion_checker import (
    AttrPromotionChecker, PROMOTION_THRESHOLD,
)


def test_promotion_threshold():
    assert PROMOTION_THRESHOLD == 20
