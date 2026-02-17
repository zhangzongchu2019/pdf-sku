"""FewShotSyncer 测试。"""
from pdf_sku.feedback.fewshot_sync import (
    FewShotSyncer, QUALITY_THRESHOLD, MIN_CONSENSUS_COUNT,
)


def test_quality_threshold():
    assert QUALITY_THRESHOLD == 0.85


def test_consensus_count():
    assert MIN_CONSENSUS_COUNT == 2


def test_hash_output_deterministic():
    syncer = FewShotSyncer()
    payload = {"product_name": "Widget", "price": "100"}
    h1 = syncer._hash_output(payload)
    h2 = syncer._hash_output(payload)
    assert h1 == h2
    assert len(h1) == 16


def test_hash_output_ignores_metadata():
    syncer = FewShotSyncer()
    p1 = {"product_name": "Widget", "annotator": "alice", "timestamp": "123"}
    p2 = {"product_name": "Widget", "annotator": "bob", "timestamp": "456"}
    assert syncer._hash_output(p1) == syncer._hash_output(p2)


def test_hash_output_different_content():
    syncer = FewShotSyncer()
    p1 = {"product_name": "Widget A"}
    p2 = {"product_name": "Widget B"}
    assert syncer._hash_output(p1) != syncer._hash_output(p2)
