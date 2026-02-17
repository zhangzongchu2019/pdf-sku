"""Docker 配置验证。"""
import os


def test_dockerfile_exists():
    path = os.path.join(os.path.dirname(__file__), "../../Dockerfile")
    assert os.path.exists(path)


def test_docker_compose_exists():
    path = os.path.join(os.path.dirname(__file__), "../../docker-compose.yml")
    assert os.path.exists(path)


def test_dockerfile_has_healthcheck():
    path = os.path.join(os.path.dirname(__file__), "../../Dockerfile")
    with open(path) as f:
        content = f.read()
    assert "HEALTHCHECK" in content
    assert "health" in content
