import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.common.models import PDFJob, StateTransition
from pdf_sku.gateway.orphan_scanner import OrphanScanner


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


@pytest.mark.asyncio
async def test_mark_orphaned_clears_worker_id_and_records_transition(monkeypatch):
    publish_mock = AsyncMock()
    monkeypatch.setattr("pdf_sku.gateway.orphan_scanner.publish_job_event", publish_mock)

    job = PDFJob(
        job_id=uuid.uuid4(),
        source_file="sample.pdf",
        file_hash="hash",
        merchant_id="merchant-1",
        uploaded_by="tester",
        status=JobInternalStatus.PROCESSING.value,
        worker_id="eval-worker-1",
    )
    db = _FakeDB()
    scanner = OrphanScanner(lambda: None, SimpleNamespace())

    await scanner._mark_orphaned(db, job)

    assert job.status == JobInternalStatus.ORPHANED.value
    assert job.worker_id is None
    assert len(db.added) == 1
    transition = db.added[0]
    assert isinstance(transition, StateTransition)
    assert transition.from_status == JobInternalStatus.PROCESSING.value
    assert transition.to_status == JobInternalStatus.ORPHANED.value
    publish_mock.assert_awaited_once()
