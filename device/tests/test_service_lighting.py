import pytest

from lighting.domain import Mode, SensorStatus, record_reading
from lighting.runtime.config import DEVICE_DIR
from lighting.service.errors import NotFoundError, RuleViolation
from lighting.service.lighting import LightingService
from lighting.sim import VirtualLight, VirtualPowerMeter
from lighting.storage import Database, load_registry

REGISTRY = load_registry(DEVICE_DIR / "device.toml")


@pytest.fixture
def lights() -> dict[int, VirtualLight]:
    return {lamp.id: VirtualLight(lamp.max_power_w, REGISTRY.lux_at_full[lamp.id]) for lamp in REGISTRY.lamps}


@pytest.fixture
def database() -> Database:
    database = Database(":memory:")
    database.seed(REGISTRY)
    return database


@pytest.fixture
def service(database: Database, lights: dict[int, VirtualLight]) -> LightingService:
    return LightingService(database, lights, VirtualPowerMeter(lights), fade_ms=600)


def run(service: LightingService, seconds: float) -> None:
    """Прогнать цикл вывода, как это делает runtime: шаг 30 мс."""
    for _ in range(round(seconds / 0.03)):
        service.tick(0.03)


def living_room(service: LightingService) -> int:
    room_id = service.create_room("Гостиная").room.id
    for lamp_id in (1, 2, 3):
        service.bind_lamp(room_id, lamp_id)
    return room_id


def test_new_room_has_defaults_and_no_lamps(service: LightingService) -> None:
    state = service.create_room("Гостиная")

    assert state.room.target_lux == 300
    assert state.lamps == []
    assert state.sensor is None
    assert state.power_w == 0


def test_power_on_lights_all_lamps_of_room_smoothly(
    service: LightingService, lights: dict[int, VirtualLight]
) -> None:
    room_id = living_room(service)

    state = service.power(room_id, on=True)
    assert state.room.brightness == 100
    run(service, 0.3)
    halfway = service.get_room(room_id)
    run(service, 0.6)
    finished = service.get_room(room_id)

    assert all(0 < lamp.lamp.brightness < 100 for lamp in halfway.lamps)
    assert [lamp.lamp.brightness for lamp in finished.lamps] == [100, 100, 100]
    assert all(lights[lamp_id].duty == pytest.approx(1.0) for lamp_id in (1, 2, 3))
    assert finished.power_w == pytest.approx(24 + 10 + 4)
    assert lights[4].duty == 0


def test_power_off_keeps_last_brightness(service: LightingService) -> None:
    room_id = living_room(service)
    service.control(room_id, brightness=40)

    service.power(room_id, on=False)
    state = service.power(room_id, on=True)

    assert state.room.brightness == 40


def test_control_applies_values_before_modes(service: LightingService, database: Database) -> None:
    room_id = living_room(service)
    sensor = record_reading(service.bind_sensor(room_id, 1).sensor, lux=100.0, cct=3000)
    # Опрос датчиков — зона telemetry; здесь просто подставляем датчик онлайн.
    service._sensors[sensor.id] = sensor

    state = service.control(room_id, brightness=40, mode="auto")

    assert state.room.mode is Mode.AUTO
    assert state.room.brightness == 40


def test_auto_without_online_sensor_is_rejected(service: LightingService) -> None:
    room_id = living_room(service)
    service.bind_sensor(room_id, 1)

    assert service.get_room(room_id).sensor.status is SensorStatus.OFFLINE
    with pytest.raises(RuleViolation):
        service.control(room_id, mode="auto")


def test_lamp_in_other_room_is_rejected(service: LightingService) -> None:
    living_room(service)
    kitchen = service.create_room("Кухня").room.id

    with pytest.raises(RuleViolation):
        service.bind_lamp(kitchen, 1)


def test_second_sensor_is_rejected(service: LightingService) -> None:
    room_id = living_room(service)
    service.bind_sensor(room_id, 1)

    with pytest.raises(RuleViolation):
        service.bind_sensor(room_id, 2)


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.get_room(99),
        lambda s: s.power(99, True),
        lambda s: s.bind_lamp(1, 99),
        lambda s: s.bind_sensor(1, 99),
        lambda s: s.rename_lamp(99, "x"),
        lambda s: s.delete_room(99),
    ],
)
def test_unknown_ids_raise_not_found(service: LightingService, call) -> None:
    service.create_room("Гостиная")

    with pytest.raises(NotFoundError):
        call(service)


def test_unbinding_lamp_of_other_room_is_not_found(service: LightingService) -> None:
    living_room(service)
    kitchen = service.create_room("Кухня").room.id

    with pytest.raises(NotFoundError):
        service.unbind_lamp(kitchen, 1)


def test_unbinding_sensor_switches_auto_to_manual(service: LightingService) -> None:
    room_id = living_room(service)
    service.bind_sensor(room_id, 1)
    service._sensors[1] = record_reading(service._sensors[1], lux=100.0, cct=3000)
    service.control(room_id, brightness=50, mode="auto")

    state = service.unbind_sensor(room_id, 1)

    assert state.room.mode is Mode.MANUAL
    assert state.room.brightness == 50


def test_deleting_room_unbinds_and_lamps_fade_out(
    service: LightingService, lights: dict[int, VirtualLight]
) -> None:
    """Инварианты 3 и 13: лампы остаются в реестре и гаснут сами."""
    room_id = living_room(service)
    service.bind_sensor(room_id, 1)
    service.power(room_id, on=True)
    run(service, 1)

    service.delete_room(room_id)
    run(service, 1)

    assert service.list_rooms() == []
    assert len(service.list_lamps(free=True)) == 8
    assert len(service.list_sensors(free=True)) == 3
    assert all(light.duty == 0 for light in lights.values())


def test_changes_are_saved_to_database(service: LightingService, database: Database) -> None:
    room_id = living_room(service)
    service.control(room_id, brightness=62, color_temp_k=3500)
    service.rename_lamp(1, "Большая люстра")
    service.update_site(tariff_rub_per_kwh=7.0)

    assert database.load_rooms()[0].brightness == 62
    assert database.load_lamps()[0].name == "Большая люстра"
    assert database.load_lamps()[0].room_id == room_id
    assert database.load_site().tariff_rub_per_kwh == 7.0


def test_free_filter_and_rename(service: LightingService) -> None:
    living_room(service)

    assert [state.lamp.id for state in service.list_lamps(free=True)] == [4, 5, 6, 7, 8]
    assert service.rename_sensor(2, "Кухонный").name == "Кухонный"


def test_first_tick_outputs_state_to_all_lamps(
    database: Database, lights: dict[int, VirtualLight]
) -> None:
    for light in lights.values():
        light.set_output(relay=True, warm=1.0, cool=0.0)
    service = LightingService(database, lights, VirtualPowerMeter(lights))

    service.tick(0.03)

    assert all(light.duty == 0 for light in lights.values())


def test_close_turns_off_all_lamps(service: LightingService, lights: dict[int, VirtualLight]) -> None:
    room_id = living_room(service)
    service.power(room_id, on=True)
    run(service, 1)

    service.close()

    assert all(light.duty == 0 for light in lights.values())
