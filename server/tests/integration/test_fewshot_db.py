"""FewShotSyncer DB 集成测试。"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pdf_sku.common.models import (
    Annotation, HumanTask, AnnotatorProfile, AnnotationExample, PDFJob)
from pdf_sku.feedback.fewshot_sync import FewShotSyncer

def _now(): return datetime.now(timezone.utc)

@pytest.mark.asyncio
async def test_fewshot_below_quality(db):
    jid = uuid4()
    db.add(PDFJob(job_id=jid, merchant_id="m_fs", source_file="t.pdf",
                  file_hash=f"fs{uuid4().hex[:8]}", total_pages=1, status="PROCESSING", user_status="PROCESSING"))
    db.add(AnnotatorProfile(annotator_id="low_scorer", accuracy_rate=0.5, total_tasks=10))
    task = HumanTask(task_id=uuid4(), job_id=jid, page_number=1,
                     task_type="SKU_REVIEW", status="COMPLETED", assigned_to="low_scorer",
                     timeout_at=_now()+timedelta(hours=4))
    db.add(task); await db.flush()
    ann = Annotation(annotation_id=uuid4(), task_id=task.task_id, job_id=jid,
                     page_number=1, type="SKU_ATTRIBUTE_CORRECTION", annotator="low_scorer",
                     annotated_at=_now(), payload={"product_name": "test"})
    db.add(ann); await db.flush()
    assert await FewShotSyncer().sync_from_task(db, task, [ann]) == 0

@pytest.mark.asyncio
async def test_fewshot_get_examples(db):
    db.add(AnnotationExample(task_type="SKU_REVIEW", category="electronics",
                             input_context="test", output_json={"product": "Widget"},
                             quality_score=0.95, is_confirmed=True))
    db.add(AnnotationExample(task_type="SKU_REVIEW", category="electronics",
                             input_context="unconfirmed", output_json={"product": "Pending"},
                             quality_score=0.90, is_confirmed=False))
    await db.flush()
    examples = await FewShotSyncer().get_examples(db, "SKU_REVIEW", "electronics")
    assert len(examples) == 1
    assert examples[0].is_confirmed is True
