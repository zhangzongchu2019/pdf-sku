"""Job 全生命周期集成测试。"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pdf_sku.common.models import PDFJob, Page, SKU, HumanTask

def _now():
    return datetime.now(timezone.utc)

@pytest.mark.asyncio
async def test_create_job(db):
    job = PDFJob(job_id=uuid4(), merchant_id="m001", source_file="catalog.pdf",
                 file_hash="abc123", total_pages=10, status="CREATED", user_status="PROCESSING")
    db.add(job); await db.flush()
    from sqlalchemy import select
    loaded = (await db.execute(select(PDFJob).where(PDFJob.job_id == job.job_id))).scalar_one()
    assert loaded.merchant_id == "m001" and loaded.total_pages == 10

@pytest.mark.asyncio
async def test_job_with_pages(db):
    jid = uuid4()
    db.add(PDFJob(job_id=jid, merchant_id="m002", source_file="t.pdf",
                  file_hash="def456", total_pages=3, status="EVALUATING", user_status="PROCESSING"))
    await db.flush()
    for i in range(1, 4): db.add(Page(job_id=jid, page_number=i, status="PENDING"))
    await db.flush()
    from sqlalchemy import select, func
    assert (await db.execute(select(func.count()).select_from(Page).where(Page.job_id == jid))).scalar() == 3

@pytest.mark.asyncio
async def test_page_status_transitions(db):
    jid = uuid4()
    db.add(PDFJob(job_id=jid, merchant_id="m003", source_file="t.pdf",
                  file_hash="ghi789", total_pages=1, status="PROCESSING", user_status="PROCESSING"))
    p = Page(job_id=jid, page_number=1, status="PENDING")
    db.add(p); await db.flush()
    p.status = "PROCESSING"; await db.flush()
    p.status = "AI_COMPLETED"; await db.flush()
    assert p.status == "AI_COMPLETED"

@pytest.mark.asyncio
async def test_sku_creation(db):
    jid = uuid4()
    db.add(PDFJob(job_id=jid, merchant_id="m004", source_file="t.pdf",
                  file_hash=f"jkl{uuid4().hex[:8]}", total_pages=1, status="PROCESSING", user_status="PROCESSING"))
    await db.flush()
    sku = SKU(sku_id=str(uuid4()), job_id=jid, page_number=1,
              attributes={"product_name": "Widget X"}, validity="valid")
    db.add(sku); await db.flush()
    from sqlalchemy import select
    loaded = (await db.execute(select(SKU).where(SKU.job_id == jid))).scalar_one()
    assert loaded.attributes["product_name"] == "Widget X"

@pytest.mark.asyncio
async def test_human_task_lifecycle(db):
    jid = uuid4()
    db.add(PDFJob(job_id=jid, merchant_id="m005", source_file="t.pdf",
                  file_hash=f"mno{uuid4().hex[:8]}", total_pages=1, status="PROCESSING", user_status="PROCESSING"))
    task = HumanTask(task_id=uuid4(), job_id=jid, page_number=1,
                     task_type="SKU_REVIEW", status="CREATED", priority="NORMAL",
                     timeout_at=_now()+timedelta(hours=4))
    db.add(task); await db.flush()
    task.status = "LOCKED"; task.assigned_to = "alice"; task.locked_at = _now()
    await db.flush()
    assert task.assigned_to == "alice"
    task.status = "COMPLETED"; await db.flush()
    assert task.status == "COMPLETED"

@pytest.mark.asyncio
async def test_job_completion_flow(db):
    jid = uuid4()
    job = PDFJob(job_id=jid, merchant_id="m006", source_file="t.pdf",
                 file_hash=f"pqr{uuid4().hex[:8]}", total_pages=2, status="PROCESSING", user_status="PROCESSING")
    db.add(job)
    for i in range(1, 3): db.add(Page(job_id=jid, page_number=i, status="IMPORTED_CONFIRMED"))
    await db.flush()
    from sqlalchemy import select, func
    terminal = (await db.execute(select(func.count()).select_from(Page).where(
        Page.job_id == jid, Page.status.in_(["AI_COMPLETED","IMPORTED_CONFIRMED","IMPORTED_ASSUMED","BLANK"])))).scalar()
    assert terminal == 2
    job.status = "FULL_IMPORTED"; job.user_status = "COMPLETED"; await db.flush()
    assert job.user_status == "COMPLETED"
