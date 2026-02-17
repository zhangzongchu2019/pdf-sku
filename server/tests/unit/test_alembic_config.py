"""Alembic 配置验证。"""
import os


def test_alembic_ini_exists():
    ini_path = os.path.join(
        os.path.dirname(__file__), "../../alembic.ini")
    assert os.path.exists(ini_path)


def test_alembic_env_exists():
    env_path = os.path.join(
        os.path.dirname(__file__), "../../alembic/env.py")
    assert os.path.exists(env_path)
