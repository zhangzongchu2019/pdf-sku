"""枚举完整性测试。对齐: 数据字典 §2"""
from pdf_sku.common.enums import *

def test_job_internal_status_has_12_values():
    assert len(JobInternalStatus) == 12

def test_job_user_status_has_5_values():
    assert len(JobUserStatus) == 5

def test_user_status_map_covers_all():
    for s in JobInternalStatus:
        assert s in USER_STATUS_MAP

def test_page_status_has_14_values():
    assert len(PageStatus) == 14

def test_sku_status_has_8_values():
    assert len(SKUStatus) == 8

def test_sse_event_type_has_9_values():
    assert len(SSEEventType) == 9

def test_annotation_type_has_8_values():
    assert len(AnnotationType) == 8

def test_image_role_deliverability():
    assert ImageRole.PRODUCT_MAIN.is_deliverable is True
    assert ImageRole.LOGO.is_deliverable is False
