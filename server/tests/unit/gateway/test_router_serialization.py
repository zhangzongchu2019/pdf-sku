import pytest
from uuid import uuid4

from pdf_sku.common.models import Image, Page, SKUImageBinding
from pdf_sku.gateway.router import _build_sku_image_maps, _job_image_url, _page_to_dict


def test_job_image_url():
    job_id = uuid4()
    assert _job_image_url(job_id, "img-1") == f"/api/v1/jobs/{job_id}/images/img-1"


def test_page_to_dict_includes_existing_page_fields():
    page = Page(
        job_id=uuid4(),
        page_number=3,
        status="AI_COMPLETED",
        page_type="B",
        extraction_method="sliced_vision",
        sku_count=7,
    )

    data = _page_to_dict(page)

    assert data["extraction_method"] == "sliced_vision"
    assert data["sku_count"] == 7


@pytest.mark.asyncio
async def test_build_sku_image_maps_includes_variant_urls(db):
    job_id = uuid4()
    db.add(Image(
        image_id="img-1",
        job_id=job_id,
        page_number=1,
        extracted_path="images/img-1.jpg",
        format="jpg",
    ))
    db.add(SKUImageBinding(
        sku_id="SKU-1",
        image_id="img-1",
        job_id=job_id,
        binding_method="spatial_proximity",
        binding_confidence=0.9,
        rank=1,
    ))
    await db.flush()

    bindings_map, image_paths_map = await _build_sku_image_maps(db, job_id, ["SKU-1"])

    assert bindings_map["SKU-1"][0]["image_url"] == f"/api/v1/jobs/{job_id}/images/img-1"
    assert bindings_map["SKU-1"][0]["thumbnail_url"] == f"/api/v1/jobs/{job_id}/images/img-1/thumbnail"
    assert bindings_map["SKU-1"][0]["preview_url"] == f"/api/v1/jobs/{job_id}/images/img-1/preview"
    assert image_paths_map["SKU-1"] == [f"/api/v1/jobs/{job_id}/images/img-1"]
