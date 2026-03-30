"""JWT security regression tests."""
from pdf_sku.auth.security import DEV_JWT_SECRET_KEY, resolve_jwt_secret_key


def test_resolve_jwt_secret_key_uses_stable_dev_default():
    assert resolve_jwt_secret_key("development", "") == DEV_JWT_SECRET_KEY
    assert resolve_jwt_secret_key("test", None) == DEV_JWT_SECRET_KEY


def test_resolve_jwt_secret_key_prefers_configured_secret():
    assert resolve_jwt_secret_key("development", "custom-secret") == "custom-secret"
    assert resolve_jwt_secret_key("production", "custom-secret") == "custom-secret"
