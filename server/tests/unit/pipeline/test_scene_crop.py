import io
from types import SimpleNamespace

import pytest
from PIL import Image

from pdf_sku.pipeline.ir import BindingResult, ImageInfo, SKUResult
from pdf_sku.pipeline.page_processor import PageProcessor


def _make_image_bytes(size: tuple[int, int] = (1000, 1000)) -> bytes:
    img = Image.new("RGB", size, color=(245, 245, 245))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class _FakeLLM:
    def __init__(self, text: str = "[]") -> None:
        self.text = text
        self.calls: list[dict] = []

    async def _call_llm(self, operation: str, prompt: str, images=None):
        self.calls.append({
            "operation": operation,
            "prompt": prompt,
            "images": images,
        })
        return SimpleNamespace(text=self.text)


@pytest.mark.asyncio
async def test_detect_product_regions_requests_promo_block_crop():
    from pdf_sku.pipeline.extractor.single_stage import SingleStageExtractor

    llm = _FakeLLM()
    extractor = SingleStageExtractor(llm_service=llm)

    await extractor.detect_product_regions(
        screenshot=_make_image_bytes((640, 960)),
        product_names=["云朵沙发"],
    )

    assert llm.calls
    prompt = llm.calls[0]["prompt"]
    assert "完整宣传图/产品卡片区域" in prompt
    assert "不要把 PDF 页面背景、页边白底、扫描留白一起框进去" in prompt
    assert "同一产品如果在页面上出现多张彼此分开的独立宣传图" in prompt
    assert "不要留白边或多余背景边" in prompt
    assert "只框选产品本身" not in prompt


def test_apply_scene_crops_keeps_exact_detected_box():
    original_img = ImageInfo(
        image_id="orig",
        bbox=(0, 0, 1000, 1000),
        data=_make_image_bytes(),
        width=1000,
        height=1000,
        short_edge=1000,
        role="unknown",
        search_eligible=True,
    )
    skus = [
        SKUResult(
            sku_id="sku-1",
            attributes={"product_name": "云朵沙发"},
            validity="valid",
        )
    ]
    bindings = [
        BindingResult(
            sku_id="sku-1",
            image_id="orig",
            confidence=0.91,
        )
    ]

    new_images, new_bindings = PageProcessor._apply_scene_crops(
        original_img=original_img,
        regions=[{"label": "云朵沙发", "bbox": [0.2, 0.2, 0.4, 0.4]}],
        skus=skus,
        bindings=bindings,
        page_no=1,
        screenshot=_make_image_bytes(),
    )

    assert len(new_images) == 1
    crop_img = new_images[0]
    assert crop_img.width == 200
    assert crop_img.height == 200
    assert crop_img.short_edge == min(crop_img.width, crop_img.height)
    assert original_img.role == "scene_full"
    assert original_img.search_eligible is False
    assert new_bindings[0].image_id == crop_img.image_id
    assert new_bindings[0].method == "scene_crop"


def test_apply_scene_crops_binds_all_regions_to_single_sku():
    original_img = ImageInfo(
        image_id="orig",
        bbox=(0, 0, 1000, 1000),
        data=_make_image_bytes(),
        width=1000,
        height=1000,
        short_edge=1000,
        role="unknown",
        search_eligible=True,
    )
    skus = [
        SKUResult(
            sku_id="sku-1",
            attributes={"product_name": "云朵沙发"},
            validity="valid",
        )
    ]
    bindings = [
        BindingResult(
            sku_id="sku-1",
            image_id="orig",
            confidence=0.91,
        )
    ]

    new_images, new_bindings = PageProcessor._apply_scene_crops(
        original_img=original_img,
        regions=[
            {"label": "云朵沙发主图", "bbox": [0.10, 0.10, 0.45, 0.55]},
            {"label": "云朵沙发副图", "bbox": [0.60, 0.18, 0.82, 0.40]},
        ],
        skus=skus,
        bindings=bindings,
        page_no=1,
        screenshot=_make_image_bytes(),
    )

    assert len(new_images) == 2
    assert [b.sku_id for b in new_bindings] == ["sku-1", "sku-1"]
    assert [b.image_id for b in new_bindings] == [new_images[0].image_id, new_images[1].image_id]
    assert [b.rank for b in new_bindings] == [1, 2]
    assert all(b.method == "scene_crop" for b in new_bindings)


def test_apply_scene_crops_keeps_large_single_page_promo_block():
    original_img = ImageInfo(
        image_id="orig",
        bbox=(0, 0, 1000, 1000),
        data=_make_image_bytes(),
        width=1000,
        height=1000,
        short_edge=1000,
        role="unknown",
        search_eligible=True,
    )
    skus = [
        SKUResult(
            sku_id="sku-1",
            attributes={"product_name": "主推床"},
            validity="valid",
        )
    ]
    bindings = [
        BindingResult(
            sku_id="sku-1",
            image_id="orig",
            confidence=0.88,
        )
    ]

    new_images, _ = PageProcessor._apply_scene_crops(
        original_img=original_img,
        regions=[{"label": "主推床", "bbox": [0.01, 0.01, 0.99, 0.98]}],
        skus=skus,
        bindings=bindings,
        page_no=1,
        screenshot=_make_image_bytes(),
    )

    assert len(new_images) == 1
    assert new_images[0].width >= 980
    assert new_images[0].height >= 970
