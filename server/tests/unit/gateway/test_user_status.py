from pdf_sku.common.enums import (
    JobInternalStatus, JobUserStatus, compute_user_status,
    USER_STATUS_MAP, ACTION_HINT_MAP,
)

def test_all_internal_statuses_mapped():
    for s in JobInternalStatus:
        result = compute_user_status(s)
        assert isinstance(result, JobUserStatus), f"{s} not mapped"

def test_upload_to_processing():
    assert compute_user_status(JobInternalStatus.UPLOADED) == JobUserStatus.PROCESSING

def test_full_imported_to_completed():
    assert compute_user_status(JobInternalStatus.FULL_IMPORTED) == JobUserStatus.COMPLETED

def test_degraded_to_needs_manual():
    assert compute_user_status(JobInternalStatus.DEGRADED_HUMAN) == JobUserStatus.NEEDS_MANUAL

def test_cancelled_to_failed():
    assert compute_user_status(JobInternalStatus.CANCELLED) == JobUserStatus.FAILED

def test_action_hints_complete():
    for us in JobUserStatus:
        assert us.value in ACTION_HINT_MAP or us in ACTION_HINT_MAP

def test_string_input():
    assert compute_user_status("UPLOADED") == JobUserStatus.PROCESSING
