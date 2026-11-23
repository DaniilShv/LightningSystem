from pathlib import Path

import pytest

from lighting.domain import ColorMode, Mode, Site, bind_lamp, bind_sensor, set_brightness, set_color_temp
from lighting.runtime.config import DEVICE_DIR
from lighting.storage import Database, load_registry

REGISTRY_PATH = DEVICE_DIR / "device.toml"

LAMP = """
[[lamps]]
id = {id}
name = "Лампа {id}"
pins = {{ relay = {relay}, warm = {warm}, cool = {cool} }}
max_power_w = 10
lux_at_full = 100
"""
SITE = '[site]\nname = "Тест"\ntariff_rub_per_kwh = 5.0\n'


def write_registry(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "device.toml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------- Реестр device.toml ----------


def test_project_registry_loads() -> None:
    registry = load_registry(REGISTRY_PATH)

    assert len(registry.lamps) == 8
    assert len(registry.sensors) == 3
    assert registry.lamps[0].pins.relay == 5
    assert registry.sensors[0].connection.address == 0x29
    assert registry.lux_at_full[1] == 400
    assert registry.window[2] == 0.8


def test_sensor_without_mux_channel_is_direct(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path, SITE + '[[sensors]]\nid = 1\nname = "Д"\nbus = "I2C-1"\naddress = 0x29\nwindow = 1.0\n'
    )

    assert load_registry(path).sensors[0].connection.mux_channel is None


def test_duplicate_pin_is_rejected(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path,
        SITE + LAMP.format(id=1, relay=5, warm=17, cool=27) + LAMP.format(id=2, relay=6, warm=17, cool=24),
    )

    with pytest.raises(ValueError, match="GPIO17"):
        load_registry(path)


def test_pin_outside_free_range_is_rejected(tmp_path: Path) -> None:
    path = write_registry(tmp_path, SITE + LAMP.format(id=1, relay=2, warm=17, cool=27))

    with pytest.raises(ValueError, match="GPIO2"):
        load_registry(path)


def test_duplicate_lamp_id_is_rejected(tmp_path: Path) -> None:
    path = write_registry(
        tmp_path, SITE + LAMP.format(id=1, relay=5, warm=17, cool=27) + LAMP.format(id=1, relay=6, warm=23, cool=24)
    )

    with pytest.raises(ValueError, match="id"):
        load_registry(path)


def test_several_sensors_need_own_mux_channels(tmp_path: Path) -> None:
    sensor = '[[sensors]]\nid = {id}\nname = "Д"\nbus = "I2C-1"\naddress = 0x29\nwindow = 1.0\n'
    path = write_registry(tmp_path, SITE + sensor.format(id=1) + sensor.format(id=2))

    with pytest.raises(ValueError, match="mux_channel"):
        load_registry(path)


# ---------- База ----------


@pytest.fixture
def database() -> Database:
    database = Database(":memory:")
    database.seed(load_registry(REGISTRY_PATH))
    return database


def test_seed_fills_registries_once(database: Database) -> None:
    assert not database.is_empty()
    assert len(database.load_lamps()) == 8
    assert len(database.load_sensors()) == 3
    assert database.load_site().name == "Квартира"

    with pytest.raises(RuntimeError):
        database.seed(load_registry(REGISTRY_PATH))


def test_new_room_gets_id_and_defaults(database: Database) -> None:
    first = database.insert_room("Гостиная", 300)
    second = database.insert_room("Кухня", 400)

    assert (first.id, second.id) == (1, 2)
    assert database.load_rooms() == [first, second]
    assert first.mode is Mode.MANUAL and first.brightness == 0


def test_room_setpoints_and_modes_round_trip(database: Database) -> None:
    room = database.insert_room("Гостиная", 300)
    room = set_color_temp(set_brightness(room, 62), 3500)

    database.save_room(room)

    assert database.load_rooms() == [room]
    assert database.load_rooms()[0].color_mode is ColorMode.MANUAL


def test_bindings_round_trip(database: Database) -> None:
    room = database.insert_room("Гостиная", 300)
    lamp = bind_lamp(database.load_lamps()[0], room.id)
    sensor = bind_sensor(database.load_sensors()[0], room.id, database.load_sensors())

    database.save_lamp(lamp)
    database.save_sensor(sensor)

    assert database.load_lamps()[0].room_id == room.id
    assert database.load_sensors()[0].room_id == room.id


def test_deleting_room_unbinds_lamps_and_sensor(database: Database) -> None:
    """Инвариант 3: удаление комнаты не удаляет лампы и датчик."""
    room = database.insert_room("Гостиная", 300)
    database.save_lamp(bind_lamp(database.load_lamps()[0], room.id))
    database.save_sensor(bind_sensor(database.load_sensors()[0], room.id, []))

    database.delete_room(room.id)

    assert database.load_rooms() == []
    assert len(database.load_lamps()) == 8
    assert database.load_lamps()[0].room_id is None
    assert database.load_sensors()[0].room_id is None


def test_site_round_trip(database: Database) -> None:
    database.save_site(Site(name="Офис", tariff_rub_per_kwh=7.5))

    assert database.load_site() == Site(name="Офис", tariff_rub_per_kwh=7.5)


def test_data_survives_restart(tmp_path: Path) -> None:
    """Инвариант 11: комнаты, уставки и привязки сохраняются между запусками."""
    path = tmp_path / "lighting.db"
    database = Database(path)
    database.seed(load_registry(REGISTRY_PATH))
    room = set_brightness(database.insert_room("Гостиная", 300), 40)
    database.save_room(room)
    database.save_lamp(bind_lamp(database.load_lamps()[2], room.id))
    database.close()

    reopened = Database(path)

    assert not reopened.is_empty()
    assert reopened.load_rooms() == [room]
    assert reopened.load_lamps()[2].room_id == room.id
    reopened.close()
