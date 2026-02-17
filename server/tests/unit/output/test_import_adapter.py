"""ImportAdapter 常量 + ImportResult 测试。"""
from pdf_sku.output.import_adapter import (
    ImportAdapter, ImportResult, ImportDataError, ImportServerError,
)


def test_import_result_dataclass():
    r = ImportResult(confirmed=True, status_code=200)
    assert r.confirmed
    assert r.status_code == 200


def test_import_result_defaults():
    r = ImportResult()
    assert not r.confirmed
    assert r.status_code == 0


def test_adapter_backoff_config():
    adapter = ImportAdapter()
    assert adapter.MAX_RETRIES == 3
    assert len(adapter.BACKOFF_429) == 3
    assert adapter.BACKOFF_429[0] == 30
    assert adapter.BACKOFF_429[2] == 120


def test_import_data_error():
    try:
        raise ImportDataError("bad data")
    except ImportDataError as e:
        assert "bad data" in str(e)


def test_import_server_error():
    try:
        raise ImportServerError("500")
    except ImportServerError as e:
        assert "500" in str(e)
