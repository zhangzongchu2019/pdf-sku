from pdf_sku.common.exceptions import *

def test_error_to_dict():
    err = FileSizeExceededError("too big")
    d = err.to_dict()
    assert d["error_code"] == "FILE_SIZE_EXCEEDED"
    assert d["severity"] == "error"
