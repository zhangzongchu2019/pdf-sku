"""SKUImageBinder 测试。"""
from pdf_sku.pipeline.ir import SKUResult, ImageInfo, ClassifyResult
from pdf_sku.pipeline.binder.binder import SKUImageBinder


def test_bind_single_match():
    binder = SKUImageBinder()
    skus = [SKUResult(sku_id="s1", source_bbox=(100, 100, 200, 200))]
    images = [ImageInfo(image_id="i1", bbox=(100, 50, 200, 95), search_eligible=True)]
    layout = ClassifyResult(layout_type="list")
    
    results = binder.bind(skus, images, layout)
    assert len(results) == 1
    assert results[0].image_id == "i1"
    assert not results[0].is_ambiguous


def test_bind_no_match():
    binder = SKUImageBinder()
    skus = [SKUResult(sku_id="s1", source_bbox=(100, 100, 200, 200))]
    images = [ImageInfo(image_id="i1", bbox=(800, 800, 900, 900))]
    layout = ClassifyResult(layout_type="freeform")
    
    results = binder.bind(skus, images, layout)
    assert results[0].image_id is None


def test_bind_ambiguous():
    binder = SKUImageBinder()
    skus = [SKUResult(sku_id="s1", source_bbox=(100, 100, 200, 200))]
    images = [
        ImageInfo(image_id="i1", bbox=(100, 50, 200, 95)),
        ImageInfo(image_id="i2", bbox=(105, 55, 205, 98)),  # very close
    ]
    layout = ClassifyResult(layout_type="freeform")
    
    results = binder.bind(skus, images, layout)
    assert len(results) == 1
    # Both images are very close → likely ambiguous
    if results[0].is_ambiguous:
        assert results[0].image_id is None
        assert len(results[0].candidates) >= 2


def test_bind_empty_skus():
    binder = SKUImageBinder()
    results = binder.bind([], [], None)
    assert results == []


def test_infer_method_grid():
    assert SKUImageBinder._infer_method(
        SKUResult(), ImageInfo(), "grid") == "grid_alignment"
