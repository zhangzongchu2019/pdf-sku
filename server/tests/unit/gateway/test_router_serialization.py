from uuid import uuid4

from pdf_sku.common.models import Page
from pdf_sku.gateway.router import _job_image_url, _page_to_dict


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
