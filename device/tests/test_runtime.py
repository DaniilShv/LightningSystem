import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lighting.hal import Clock, SensorError
from lighting.runtime.config import Settings
from lighting.runtime.main import create_app, output_loop

KEY = {"X-API-Key": "secret"}


def make_settings(tmp_path: Path, runtime: str = "virtual", fade_ms: float = 600) -> Settings:
    return Settings(_env_file=None, runtime=runtime, api_key="secret", db_path=tmp_path / "test.db", fade_ms=fade_ms)


def poll_sensors(app) -> None:
    """То, что будет делать цикл опроса датчиков Максима: прочитать и передать замер в service."""
    service = app.state.lighting_service
    for sensor_id, driver in app.state.sensor_drivers.items():
        try:
            reading = driver.read()
        except SensorError:
            service.record_sensor_failure(sensor_id)
        else:
            service.record_sensor_reading(sensor_id, reading.lux, reading.cct)


def test_output_loop_fades_lamps_in_running_app(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path)), headers=KEY) as client:
        room_id = client.post("/api/v1/rooms", json={"name": "Гостиная"}).json()["id"]
        client.put(f"/api/v1/rooms/{room_id}/lamps/1")
        client.post(f"/api/v1/rooms/{room_id}/power", json={"on": True})

        # Цикл вывода работает в фоне: даём ему время, а не вызываем вручную.
        deadline = time.monotonic() + 3
        lamp = client.get("/api/v1/lamps").json()[0]
        while lamp["brightness"] < 100 and time.monotonic() < deadline:
            time.sleep(0.05)
            lamp = client.get("/api/v1/lamps").json()[0]

    assert lamp["brightness"] == 100
    assert lamp["power_w"] == 24


def test_lamps_are_turned_off_on_shutdown(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path))
    with TestClient(app, headers=KEY) as client:
        room_id = client.post("/api/v1/rooms", json={"name": "Гостиная"}).json()["id"]
        client.put(f"/api/v1/rooms/{room_id}/lamps/1")
        client.post(f"/api/v1/rooms/{room_id}/power", json={"on": True})
        time.sleep(1)
        service = app.state.lighting_service

    assert all(light.duty == 0 for light in service._lights.values())


def test_hardware_runtime_starts_without_i2c(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """В hardware лампы — GpioLight (в тестах ножки виртуальные, conftest). На ПК нет шины I2C:
    датчики не создаются, но устройство работает, а причина видна в логе."""
    app = create_app(make_settings(tmp_path, "hardware"))
    with caplog.at_level(logging.ERROR), TestClient(app, headers=KEY) as client:
        assert client.get("/api/v1/health").json()["runtime"] == "hardware"
        assert len(client.get("/api/v1/lamps").json()) == 8
        assert app.state.sensor_drivers == {}

    assert sum("не подключён" in record.message for record in caplog.records) == 3


def test_virtual_sensors_see_only_their_lamps(tmp_path: Path) -> None:
    app = create_app(make_settings(tmp_path, fade_ms=0))
    with TestClient(app, headers=KEY) as client:
        app.state.clock.set_time(datetime(2026, 11, 23, 23, 0).astimezone())
        room_id = client.post("/api/v1/rooms", json={"name": "Кухня"}).json()["id"]
        # Лампу «Люстра» из гостиной привязываем к кухне: физически она осталась в гостиной.
        client.put(f"/api/v1/rooms/{room_id}/lamps/1")
        client.post(f"/api/v1/rooms/{room_id}/power", json={"on": True})
        time.sleep(0.3)

        sensors = app.state.sensor_drivers
        living, kitchen = sensors[1].read().lux, sensors[2].read().lux

    assert len(sensors) == 3
    assert living == pytest.approx(400, rel=0.03)
    assert kitchen == 0


def test_auto_mode_works_through_api(tmp_path: Path) -> None:
    """Вся цепочка: API → service → регулятор → цикл вывода → виртуальные лампы → виртуальный датчик."""
    app = create_app(make_settings(tmp_path, fade_ms=0))
    with TestClient(app, headers=KEY) as client:
        clock = app.state.clock
        clock.set_time(datetime(2026, 11, 23, 23, 0).astimezone())
        # Ускоряем время ×10: замер раз в 0,1 с реального времени = раз в секунду по часам устройства.
        clock.set_speed(10)
        room_id = client.post("/api/v1/rooms", json={"name": "Гостиная", "target_lux": 300}).json()["id"]
        for lamp_id in (1, 2, 3):
            client.put(f"/api/v1/rooms/{room_id}/lamps/{lamp_id}")
        client.put(f"/api/v1/rooms/{room_id}/sensor/1")

        assert client.patch(f"/api/v1/rooms/{room_id}/control", json={"mode": "auto"}).status_code == 409
        poll_sensors(app)
        assert client.patch(f"/api/v1/rooms/{room_id}/control", json={"mode": "auto"}).status_code == 200

        for _ in range(30):
            time.sleep(0.1)
            poll_sensors(app)
        room = client.get(f"/api/v1/rooms/{room_id}").json()

    assert room["mode"] == "auto"
    assert room["sensor"]["status"] == "online"
    assert 0 < room["brightness"] < 100
    assert abs(room["sensor"]["lux"] - 300) <= 30


class BrokenService:
    def __init__(self) -> None:
        self.calls = 0

    def tick(self, dt: float) -> None:
        self.calls += 1
        raise RuntimeError("сбой")


class StepClock(Clock):
    def __init__(self) -> None:
        self.moment = datetime(2026, 11, 23, 20, 0).astimezone()

    def now(self) -> datetime:
        self.moment += timedelta(milliseconds=30)
        return self.moment


def test_output_loop_survives_errors() -> None:
    service = BrokenService()

    async def run_briefly() -> None:
        task = asyncio.create_task(output_loop(service, StepClock()))
        await asyncio.sleep(0.2)
        task.cancel()

    asyncio.run(run_briefly())

    assert service.calls > 1
