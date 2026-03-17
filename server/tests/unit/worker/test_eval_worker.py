import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pdf_sku.common.models import PDFJob
from pdf_sku.worker.eval_worker import EvalWorker


class _FakeResult:
    def __init__(self, job):
        self._job = job

    def scalar_one_or_none(self):
        return self._job


class _FakeDB:
    def __init__(self, job):
        self.job = job
        self.commit = AsyncMock()

    async def execute(self, _stmt):
        return _FakeResult(self.job)


class _SessionFactory:
    def __init__(self, db):
        self._db = db

    def __call__(self):
        db = self._db

        class _Ctx:
            async def __aenter__(self):
                return db

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


@pytest.mark.asyncio
async def test_run_evaluation_commits_before_return():
    job = PDFJob(
        job_id=uuid.uuid4(),
        source_file="sample.pdf",
        file_hash="hash",
        merchant_id="merchant-1",
        uploaded_by="tester",
    )
    db = _FakeDB(job)
    worker = EvalWorker(_SessionFactory(db), redis=None)
    evaluator = SimpleNamespace(evaluate=AsyncMock(return_value={"route": "HYBRID"}))
    worker.set_evaluator_service(evaluator)

    result = await worker._run_evaluation(job, {"prescan": {}})

    assert result == {"route": "HYBRID"}
    evaluator.evaluate.assert_awaited_once()
    db.commit.assert_awaited_once()
