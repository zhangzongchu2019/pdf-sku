"""pipeline 工厂选择测试。"""
from pdf_sku.pipeline_factory import build_page_processor, normalize_pipeline_implementation


class _LegacyStub:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _V2Stub:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_normalize_pipeline_implementation():
    assert normalize_pipeline_implementation("legacy") == "legacy"
    assert normalize_pipeline_implementation("V2") == "v2"
    assert normalize_pipeline_implementation("unknown") == "legacy"


def test_build_page_processor_selects_target_implementation():
    legacy = build_page_processor(
        pipeline_implementation="legacy",
        _legacy_cls=_LegacyStub,
        _v2_cls=_V2Stub,
    )
    assert isinstance(legacy, _LegacyStub)

    v2 = build_page_processor(
        pipeline_implementation="v2",
        _legacy_cls=_LegacyStub,
        _v2_cls=_V2Stub,
    )
    assert isinstance(v2, _V2Stub)
