from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lighting.runtime.config import Settings
from lighting.runtime.main import create_app

KEY = {"X-API-Key": "secret"}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, runtime="virtual", api_key="secret", db_path=tmp_path / "test.db", fade_ms=0)
    # with — чтобы выполнился lifespan: база, драйверы и цикл вывода.
    with TestClient(create_app(settings), headers=KEY) as client:
        yield client


def create_living_room(client: TestClient) -> int:
    room_id = client.post("/api/v1/rooms", json={"name": "Гостиная"}).json()["id"]
    for lamp_id in (1, 2):
        client.put(f"/api/v1/rooms/{room_id}/lamps/{lamp_id}")
    return room_id


def test_room_endpoints_need_key(client: TestClient) -> None:
    response = client.get("/api/v1/rooms", headers={"X-API-Key": "wrong"})

    assert response.status_code == 401


def test_create_room_returns_201_and_room_shape(client: TestClient) -> None:
    response = client.post("/api/v1/rooms", json={"name": "Гостиная", "target_lux": 250})

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Гостиная",
        "is_on": False,
        "mode": "manual",
        "brightness": 0,
        "last_brightness": 100,
        "target_lux": 250,
        "color_mode": "manual",
        "color_temp_k": 4000,
        "sensor": None,
        "lamps": [],
        "power_w": 0,
    }


def test_power_on_and_lamps_reach_setpoint(client: TestClient) -> None:
    room_id = create_living_room(client)

    room = client.post(f"/api/v1/rooms/{room_id}/power", json={"on": True}).json()

    assert room["is_on"] is True
    assert room["brightness"] == 100


def test_control_and_patch(client: TestClient) -> None:
    room_id = create_living_room(client)

    controlled = client.patch(f"/api/v1/rooms/{room_id}/control", json={"brightness": 62, "color_temp_k": 3500})
    renamed = client.patch(f"/api/v1/rooms/{room_id}", json={"name": "Зал"})

    assert controlled.status_code == 200
    assert (controlled.json()["brightness"], controlled.json()["color_temp_k"]) == (62, 3500)
    assert renamed.json()["name"] == "Зал"
    assert renamed.json()["brightness"] == 62


def test_auto_without_sensor_is_409(client: TestClient) -> None:
    room_id = create_living_room(client)

    response = client.patch(f"/api/v1/rooms/{room_id}/control", json={"mode": "auto"})

    assert response.status_code == 409
    assert "датчик" in response.json()["detail"]


def test_lamp_in_other_room_is_409(client: TestClient) -> None:
    create_living_room(client)
    kitchen = client.post("/api/v1/rooms", json={"name": "Кухня"}).json()["id"]

    assert client.put(f"/api/v1/rooms/{kitchen}/lamps/1").status_code == 409


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/rooms/99"),
        ("delete", "/api/v1/rooms/99"),
        ("put", "/api/v1/rooms/1/lamps/99"),
        ("delete", "/api/v1/rooms/1/sensor/1"),
    ],
)
def test_unknown_or_unbound_is_404(client: TestClient, method: str, path: str) -> None:
    client.post("/api/v1/rooms", json={"name": "Гостиная"})

    response = client.request(method, path)

    assert response.status_code == 404
    assert response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [{"brightness": 101}, {"brightness": -1}, {"color_temp_k": 2000}, {"mode": "turbo"}],
)
def test_invalid_control_is_422(client: TestClient, body: dict) -> None:
    room_id = create_living_room(client)

    assert client.patch(f"/api/v1/rooms/{room_id}/control", json=body).status_code == 422


def test_invalid_room_data_is_422(client: TestClient) -> None:
    assert client.post("/api/v1/rooms", json={"name": ""}).status_code == 422
    assert client.post("/api/v1/rooms", json={"name": "Кухня", "target_lux": 0}).status_code == 422


def test_delete_room_is_204_and_frees_lamps(client: TestClient) -> None:
    room_id = create_living_room(client)

    response = client.delete(f"/api/v1/rooms/{room_id}")

    assert response.status_code == 204
    assert client.get("/api/v1/rooms").json() == []
    assert len(client.get("/api/v1/lamps", params={"free": True}).json()) == 8


def test_sensor_binding_shows_offline_sensor_without_readings(client: TestClient) -> None:
    room_id = create_living_room(client)

    room = client.put(f"/api/v1/rooms/{room_id}/sensor/1").json()

    assert room["sensor"] == {"id": 1, "status": "offline", "lux": None, "cct": None}
    assert client.put(f"/api/v1/rooms/{room_id}/sensor/2").status_code == 409


def test_lamps_and_sensors_registry(client: TestClient) -> None:
    create_living_room(client)

    lamps = client.get("/api/v1/lamps").json()
    free = client.get("/api/v1/lamps", params={"free": True}).json()
    renamed = client.patch("/api/v1/lamps/1", json={"name": "Люстра в зале"}).json()
    sensors = client.get("/api/v1/sensors").json()

    assert len(lamps) == 8 and len(free) == 6
    assert set(lamps[0]) == {"id", "name", "room_id", "brightness", "color_temp_k", "power_w"}
    assert renamed["name"] == "Люстра в зале"
    assert sensors[0] == {"id": 1, "name": "Гостиная", "room_id": None, "status": "offline", "lux": None, "cct": None}
    assert client.patch("/api/v1/sensors/99", json={"name": "x"}).status_code == 404


def test_site_get_and_patch(client: TestClient) -> None:
    assert client.get("/api/v1/site").json() == {"name": "Квартира", "tariff_rub_per_kwh": 6.0}

    updated = client.patch("/api/v1/site", json={"tariff_rub_per_kwh": 7.5}).json()

    assert updated == {"name": "Квартира", "tariff_rub_per_kwh": 7.5}
    assert client.patch("/api/v1/site", json={"tariff_rub_per_kwh": -1}).status_code == 422


def test_state_survives_restart(tmp_path: Path) -> None:
    """Инвариант 11: после перезапуска комната, уставка и привязки на месте."""
    settings = Settings(_env_file=None, api_key="secret", db_path=tmp_path / "test.db", fade_ms=0)
    with TestClient(create_app(settings), headers=KEY) as client:
        room_id = create_living_room(client)
        client.patch(f"/api/v1/rooms/{room_id}/control", json={"brightness": 40})

    with TestClient(create_app(settings), headers=KEY) as client:
        room = client.get(f"/api/v1/rooms/{room_id}").json()

    assert room["brightness"] == 40
    assert [lamp["id"] for lamp in room["lamps"]] == [1, 2]


def test_swagger_lists_room_routes(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/rooms/{room_id}/control" in paths
    assert {"401", "404", "409", "422"} <= set(paths["/api/v1/rooms/{room_id}/control"]["patch"]["responses"])
