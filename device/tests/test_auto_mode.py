"""Авто-режим целиком: service + регулятор + виртуальные лампы и датчик на параметрах из device.toml.

Здесь мы сами делаем то, что потом будет делать цикл датчиков (telemetry): раз в секунду читаем
виртуальный датчик и передаём замер в service. Цикл вывода — шаги по 30 мс, как в runtime.
"""

from datetime import datetime, timedelta, timezone

import pytest

from lighting.domain import Mode, SensorStatus
from lighting.hal import Clock, SensorError
from lighting.runtime.config import DEVICE_DIR
from lighting.service.errors import NotFoundError
from lighting.service.lighting import LightingService
from lighting.sim import VirtualLight, VirtualPowerMeter, VirtualSensor
from lighting.storage import Database, load_registry

REGISTRY = load_registry(DEVICE_DIR / "device.toml")
TZ = timezone(timedelta(hours=5))
NIGHT = datetime(2026, 11, 23, 23, 0, tzinfo=TZ)
NOON = datetime(2026, 11, 23, 12, 15, tzinfo=TZ)
ROOMS = {
    # комната: (лампы, датчик, цель lux)
    "Гостиная": ((1, 2, 3), 1, 300),
    "Кухня": ((4, 5), 2, 400),
    "Спальня": ((6, 7), 3, 200),
}
TICK_S = 0.03


class ManualClock(Clock):
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


class Apartment:
    """Квартира на виртуальном железе и часы, которые двигаем сами."""

    def __init__(self, moment: datetime, noise: float = 0.0, fade_ms: float = 600) -> None:
        self.clock = ManualClock(moment)
        self.lights = {lamp.id: VirtualLight(lamp.max_power_w, REGISTRY.lux_at_full[lamp.id]) for lamp in REGISTRY.lamps}
        database = Database(":memory:")
        database.seed(REGISTRY)
        self.service = LightingService(database, self.lights, VirtualPowerMeter(self.lights), fade_ms=fade_ms)
        self.sensors: dict[int, VirtualSensor] = {}
        self.room_ids: dict[str, int] = {}
        for name, (lamp_ids, sensor_id, target) in ROOMS.items():
            room_id = self.service.create_room(name, target).room.id
            for lamp_id in lamp_ids:
                self.service.bind_lamp(room_id, lamp_id)
            self.service.bind_sensor(room_id, sensor_id)
            self.sensors[sensor_id] = VirtualSensor(
                clock=self.clock,
                window=REGISTRY.window[sensor_id],
                lamps=[self.lights[lamp_id] for lamp_id in lamp_ids],
                noise=noise,
            )
            self.room_ids[name] = room_id

    def read_sensors(self) -> None:
        for sensor_id, sensor in self.sensors.items():
            try:
                reading = sensor.read()
            except SensorError:
                self.service.record_sensor_failure(sensor_id)
            else:
                self.service.record_sensor_reading(sensor_id, reading.lux, reading.cct)

    def run(self, seconds: int) -> list[dict[str, float]]:
        """Прогнать время: каждую секунду замер, между замерами — цикл вывода. Возвращает уставки по секундам."""
        history = []
        for _ in range(seconds):
            for _ in range(round(1 / TICK_S)):
                self.clock.moment += timedelta(seconds=TICK_S)
                self.service.tick(TICK_S)
            self.read_sensors()
            history.append({name: self.room(name).room.brightness for name in ROOMS})
        return history

    def room(self, name: str):
        return self.service.get_room(self.room_ids[name])

    def switch_to_auto(self) -> None:
        self.read_sensors()  # первый замер — датчики онлайн
        for room_id in self.room_ids.values():
            self.service.control(room_id, mode="auto")


@pytest.mark.parametrize("name", ROOMS)
def test_night_auto_reaches_target_and_settles(name: str) -> None:
    apartment = Apartment(NIGHT)
    apartment.switch_to_auto()

    history = apartment.run(30)

    target = ROOMS[name][2]
    lux = apartment.sensors[ROOMS[name][1]].read().lux
    assert abs(lux - target) <= 0.1 * target
    # Последние 20 секунд уставка не меняется: свет не дёргается.
    assert len({second[name] for second in history[10:]}) == 1


@pytest.mark.parametrize("name", ROOMS)
def test_auto_converges_within_a_few_steps(name: str) -> None:
    apartment = Apartment(NIGHT)
    apartment.switch_to_auto()

    history = apartment.run(15)

    changes = sum(1 for before, after in zip(history, history[1:]) if before[name] != after[name])
    assert history[-1][name] > 0
    # Без раскачки: до цели — 0..100 % шагами по 10, потом ещё пара поправок.
    assert changes <= 12


def test_bright_day_turns_light_off() -> None:
    apartment = Apartment(NOON)
    for room_id in apartment.room_ids.values():
        apartment.service.power(room_id, on=True)
    apartment.switch_to_auto()

    apartment.run(20)

    for name in ROOMS:
        room = apartment.room(name).room
        assert room.brightness == 0
        assert room.mode is Mode.AUTO
        # Инвариант 6: последняя ненулевая уставка — последний шаг регулятора перед нулём.
        assert room.last_brightness == 10


def test_auto_follows_dusk() -> None:
    apartment = Apartment(datetime(2026, 11, 23, 16, 0, tzinfo=TZ))
    apartment.switch_to_auto()
    apartment.run(10)
    afternoon = apartment.room("Гостиная").room.brightness

    apartment.clock.moment = datetime(2026, 11, 23, 18, 0, tzinfo=TZ)
    apartment.run(30)

    assert apartment.room("Гостиная").room.brightness > afternoon


def test_sensor_noise_does_not_make_light_flicker() -> None:
    apartment = Apartment(NIGHT, noise=0.02)
    apartment.switch_to_auto()

    history = apartment.run(60)

    for name in ROOMS:
        assert len({second[name] for second in history[20:]}) == 1


def test_slow_fade_does_not_cause_overshoot() -> None:
    """Переход 3 с длиннее секунды между замерами: регулятор ждёт, пока лампы дойдут до уставки."""
    apartment = Apartment(NIGHT, fade_ms=3000)
    apartment.switch_to_auto()

    history = apartment.run(60)

    for name in ROOMS:
        target = ROOMS[name][2]
        lux = apartment.sensors[ROOMS[name][1]].read().lux
        assert abs(lux - target) <= 0.1 * target
        assert len({second[name] for second in history[-15:]}) == 1


def test_regulator_waits_while_lamps_fade() -> None:
    apartment = Apartment(NIGHT, fade_ms=3000)
    apartment.switch_to_auto()
    room_id = apartment.room_ids["Гостиная"]
    apartment.service.record_sensor_reading(1, lux=0, cct=None)
    first_step = apartment.service.get_room(room_id).room.brightness

    apartment.service.record_sensor_reading(1, lux=0, cct=None)

    assert first_step == 10
    assert apartment.service.get_room(room_id).room.brightness == 10


def test_manual_room_is_not_regulated() -> None:
    apartment = Apartment(NIGHT)
    apartment.read_sensors()
    room_id = apartment.room_ids["Гостиная"]
    apartment.service.control(room_id, brightness=20)

    apartment.run(5)

    assert apartment.service.get_room(room_id).room.brightness == 20


def test_user_takes_control_from_auto() -> None:
    """Инвариант 9: ручная яркость в авто переводит в manual, регулятор больше не трогает уставку."""
    apartment = Apartment(NIGHT)
    apartment.switch_to_auto()
    apartment.run(5)
    room_id = apartment.room_ids["Гостиная"]

    apartment.service.control(room_id, brightness=15)
    apartment.run(5)

    room = apartment.service.get_room(room_id).room
    assert room.mode is Mode.MANUAL
    assert room.brightness == 15


def test_sensor_loss_keeps_light_and_switches_to_manual() -> None:
    """Инвариант 8: после 3 ошибок подряд — manual, уставка остаётся; датчик вернулся — авто сам не включается."""
    apartment = Apartment(NIGHT)
    apartment.switch_to_auto()
    apartment.run(15)
    room_id = apartment.room_ids["Гостиная"]
    setpoint = apartment.service.get_room(room_id).room.brightness

    apartment.sensors[1].break_wire()
    apartment.run(2)
    assert apartment.service.get_room(room_id).room.mode is Mode.AUTO
    apartment.run(1)

    lost = apartment.service.get_room(room_id)
    assert lost.room.mode is Mode.MANUAL
    assert lost.room.brightness == setpoint
    assert lost.sensor.status is SensorStatus.OFFLINE
    assert lost.sensor.lux is None

    apartment.sensors[1].repair()
    apartment.run(3)

    back = apartment.service.get_room(room_id)
    assert back.sensor.status is SensorStatus.ONLINE
    assert back.room.mode is Mode.MANUAL


def test_unbound_sensor_only_updates_its_readings() -> None:
    apartment = Apartment(NIGHT)
    apartment.service.unbind_sensor(apartment.room_ids["Гостиная"], 1)

    sensor = apartment.service.record_sensor_reading(1, lux=123.0, cct=4000)

    assert (sensor.status, sensor.lux, sensor.room_id) == (SensorStatus.ONLINE, 123.0, None)


def test_unknown_sensor_is_not_found() -> None:
    apartment = Apartment(NIGHT)

    with pytest.raises(NotFoundError):
        apartment.service.record_sensor_reading(99, lux=1.0, cct=None)
    with pytest.raises(NotFoundError):
        apartment.service.record_sensor_failure(99)
