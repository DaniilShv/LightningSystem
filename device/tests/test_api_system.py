from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from lighting.runtime.config import Settings
from lighting.runtime.main import create_app


def make_client(api_key: str) -> TestClient:
    settings = Settings(_env_file=None, runtime="virtual", api_key=api_key, device_name="Тест")
    return TestClient(create_app(settings))


@pytest.fixture
def client() -> TestClient:
    return make_client("secret")


def test_health_without_key(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Тест"
    assert body["runtime"] == "virtual"
    assert body["version"]
    # ISO 8601 с часовым поясом устройства
    assert datetime.fromisoformat(body["time"]).tzinfo is not None


def test_auth_check_without_key(client: TestClient) -> None:
    response = client.get("/api/v1/auth/check")

    assert response.status_code == 401
    assert response.json()["detail"]


def test_auth_check_wrong_key(client: TestClient) -> None:
    response = client.get("/api/v1/auth/check", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_auth_check_with_key(client: TestClient) -> None:
    response = client.get("/api/v1/auth/check", headers={"X-API-Key": "secret"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_empty_key_disables_check() -> None:
    response = make_client("").get("/api/v1/auth/check")

    assert response.status_code == 200


def test_health_reports_hardware_runtime() -> None:
    settings = Settings(_env_file=None, runtime="hardware", api_key="")
    client = TestClient(create_app(settings))

    assert client.get("/api/v1/health").json()["runtime"] == "hardware"
