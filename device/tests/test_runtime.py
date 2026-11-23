import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from lighting.hal import Clock
from lighting.runtime.config import Settings
from lighting.runtime.main import create_app, output_loop

KEY = {"X-API-Key": "secret"}


def make_settings(tmp_path: Path, runtime: str = "virtual") -> Settings:
    return Settings(_env_file=None, runtime=runtime, api_key="secret", db_path=tmp_path / "test.db")


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


def test_hardware_runtime_starts_with_gpio_lamps(tmp_path: Path) -> None:
    """В hardware драйверы — GpioLight. В тестах ножки виртуальные (conftest)."""
    with TestClient(create_app(make_settings(tmp_path, "hardware")), headers=KEY) as client:
        assert client.get("/api/v1/health").json()["runtime"] == "hardware"
        assert len(client.get("/api/v1/lamps").json()) == 8


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
