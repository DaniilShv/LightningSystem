from datetime import datetime, timedelta, timezone

import pytest

from lighting.domain import (
    ColorMode,
    Lamp,
    LampPins,
    Mode,
    Room,
    RuleViolation,
    Sensor,
    SensorConnection,
    SensorStatus,
    apply_auto_brightness,
    apply_circadian_color_temp,
    bind_lamp,
    bind_sensor,
    energy_record,
    on_sensor_lost,
    record_failed_read,
    record_reading,
    set_brightness,
    set_color_mode,
    set_color_temp,
    set_mode,
    turn_off,
    turn_on,
    unbind_lamp,
    unbind_sensor,
)

NOW = datetime(2026, 11, 8, 20, 0, tzinfo=timezone(timedelta(hours=5)))
CONNECTION = SensorConnection(bus="I2C-1", address=0x29)


def make_room(**fields) -> Room:
    return Room(id=1, name="Гостиная", **fields)


def make_lamp(room_id: int | None = None) -> Lamp:
    return Lamp(id=1, name="Люстра", pins=LampPins(5, 17, 27), max_power_w=24, room_id=room_id)


def make_sensor(sensor_id: int = 1, room_id: int | None = None) -> Sensor:
    return Sensor(id=sensor_id, name="Датчик", connection=CONNECTION, room_id=room_id)


def online_sensor(room_id: int = 1) -> Sensor:
    return record_reading(make_sensor(room_id=room_id), lux=200.0, cct=4000)


# ---------- Значения по умолчанию и проверки ----------


def test_new_room_is_dark_and_manual() -> None:
    room = make_room()

    assert room.mode is Mode.MANUAL
    assert room.color_mode is ColorMode.MANUAL
    assert room.brightness == 0
    assert room.last_brightness == 100


@pytest.mark.parametrize(
    "fields",
    [
        {"brightness": -1},
        {"brightness": 101},
        {"last_brightness": 0},
        {"color_temp_k": 2699},
        {"color_temp_k": 6501},
        {"target_lux": 0},
    ],
)
def test_room_rejects_invalid_values(fields: dict) -> None:
    with pytest.raises(ValueError):
        make_room(**fields)


def test_rules_do_not_change_original_room() -> None:
    room = make_room(brightness=50, last_brightness=50)

    turn_off(room)

    assert room.brightness == 50


# ---------- Инварианты 1–3: привязки ----------


def test_lamp_in_other_room_cannot_be_bound() -> None:
    with pytest.raises(RuleViolation):
        bind_lamp(make_lamp(room_id=2), room_id=1)


def test_free_lamp_is_bound_and_rebinding_same_room_is_allowed() -> None:
    lamp = bind_lamp(make_lamp(), room_id=1)

    assert lamp.room_id == 1
    assert bind_lamp(lamp, room_id=1).room_id == 1


def test_sensor_in_other_room_cannot_be_bound() -> None:
    sensor = make_sensor(room_id=2)

    with pytest.raises(RuleViolation):
        bind_sensor(sensor, room_id=1, all_sensors=[sensor])


def test_room_with_sensor_cannot_get_second_one() -> None:
    first = make_sensor(sensor_id=1, room_id=1)
    second = make_sensor(sensor_id=2)

    with pytest.raises(RuleViolation):
        bind_sensor(second, room_id=1, all_sensors=[first, second])


def test_sensor_can_be_bound_to_free_room_and_rebound_to_same_room() -> None:
    other = make_sensor(sensor_id=2, room_id=2)
    sensor = bind_sensor(make_sensor(), room_id=1, all_sensors=[other])

    assert sensor.room_id == 1
    assert bind_sensor(sensor, room_id=1, all_sensors=[sensor, other]).room_id == 1


def test_unbinding_keeps_lamp_and_sensor_in_registry() -> None:
    lamp = unbind_lamp(make_lamp(room_id=1))
    sensor = unbind_sensor(make_sensor(room_id=1))

    assert (lamp.id, lamp.room_id) == (1, None)
    assert (sensor.id, sensor.room_id) == (1, None)


# ---------- Инвариант 5–6: включить и выключить ----------


def test_turn_off_sets_zero_and_keeps_last_brightness() -> None:
    room = turn_off(make_room(brightness=40, last_brightness=40))

    assert room.brightness == 0
    assert room.last_brightness == 40


def test_turn_on_returns_last_brightness() -> None:
    room = turn_on(turn_off(set_brightness(make_room(), 40)))

    assert room.brightness == 40


def test_turn_on_without_previous_brightness_gives_100() -> None:
    assert turn_on(make_room()).brightness == 100


def test_slider_at_zero_does_not_erase_last_brightness() -> None:
    room = set_brightness(set_brightness(make_room(), 60), 0)

    assert room.last_brightness == 60
    assert turn_on(room).brightness == 60


# ---------- Инвариант 7: авто только с датчиком онлайн ----------


def test_auto_requires_sensor() -> None:
    with pytest.raises(RuleViolation):
        set_mode(make_room(), Mode.AUTO, sensor=None)


def test_auto_requires_online_sensor() -> None:
    with pytest.raises(RuleViolation):
        set_mode(make_room(), Mode.AUTO, sensor=make_sensor(room_id=1))


def test_auto_requires_sensor_of_this_room() -> None:
    with pytest.raises(RuleViolation):
        set_mode(make_room(), Mode.AUTO, sensor=online_sensor(room_id=2))


def test_auto_with_online_sensor_is_allowed_and_keeps_setpoint() -> None:
    room = set_mode(make_room(brightness=30, last_brightness=30), Mode.AUTO, sensor=online_sensor())

    assert room.mode is Mode.AUTO
    assert room.brightness == 30


def test_manual_never_needs_sensor() -> None:
    room = set_mode(make_room(mode=Mode.AUTO), Mode.MANUAL, sensor=None)

    assert room.mode is Mode.MANUAL


# ---------- Инвариант 8: потеря датчика ----------


def test_sensor_loss_switches_to_manual_and_keeps_setpoint() -> None:
    room = on_sensor_lost(make_room(mode=Mode.AUTO, brightness=62, last_brightness=62))

    assert room.mode is Mode.MANUAL
    assert room.brightness == 62


def test_sensor_goes_offline_only_after_three_failures_in_a_row() -> None:
    sensor = online_sensor()

    sensor = record_failed_read(sensor)
    sensor = record_failed_read(sensor)
    assert sensor.status is SensorStatus.ONLINE
    assert sensor.lux == 200

    sensor = record_failed_read(sensor)
    assert sensor.status is SensorStatus.OFFLINE
    assert sensor.lux is None
    assert sensor.cct is None


def test_successful_read_resets_failure_count() -> None:
    sensor = record_failed_read(record_failed_read(online_sensor()))

    sensor = record_reading(sensor, lux=150.0, cct=3000)
    sensor = record_failed_read(record_failed_read(sensor))

    assert sensor.status is SensorStatus.ONLINE


def test_new_sensor_is_offline_until_first_reading() -> None:
    assert make_sensor().status is SensorStatus.OFFLINE
    assert online_sensor().status is SensorStatus.ONLINE


def test_auto_does_not_return_when_sensor_comes_back() -> None:
    room = on_sensor_lost(make_room(mode=Mode.AUTO))
    sensor = record_reading(make_sensor(room_id=1), lux=100.0, cct=3000)

    assert sensor.status is SensorStatus.ONLINE
    assert room.mode is Mode.MANUAL
    assert apply_auto_brightness(room, 80) == room


# ---------- Инвариант 9: ручные действия и независимость режимов ----------


def test_manual_brightness_switches_auto_to_manual() -> None:
    room = set_brightness(make_room(mode=Mode.AUTO), 40)

    assert room.mode is Mode.MANUAL
    assert room.brightness == 40


def test_turn_on_and_off_switch_auto_to_manual() -> None:
    assert turn_off(make_room(mode=Mode.AUTO)).mode is Mode.MANUAL
    assert turn_on(make_room(mode=Mode.AUTO)).mode is Mode.MANUAL


def test_manual_brightness_does_not_touch_color_mode() -> None:
    room = set_brightness(make_room(color_mode=ColorMode.CIRCADIAN), 40)

    assert room.color_mode is ColorMode.CIRCADIAN


def test_manual_color_temp_switches_only_color_mode() -> None:
    room = set_color_temp(make_room(mode=Mode.AUTO, color_mode=ColorMode.CIRCADIAN), 3000)

    assert room.color_mode is ColorMode.MANUAL
    assert room.color_temp_k == 3000
    assert room.mode is Mode.AUTO


def test_color_mode_change_does_not_touch_brightness_mode() -> None:
    room = set_color_mode(make_room(mode=Mode.AUTO), ColorMode.CIRCADIAN)

    assert room.color_mode is ColorMode.CIRCADIAN
    assert room.mode is Mode.AUTO


# ---------- Решения регуляторов ----------


def test_auto_decision_keeps_auto_mode_and_updates_last_brightness() -> None:
    room = apply_auto_brightness(make_room(mode=Mode.AUTO), 45)

    assert room.mode is Mode.AUTO
    assert room.brightness == 45
    assert room.last_brightness == 45


def test_auto_decision_to_zero_keeps_last_brightness() -> None:
    room = apply_auto_brightness(make_room(mode=Mode.AUTO, brightness=30, last_brightness=30), 0)

    assert room.brightness == 0
    assert room.last_brightness == 30


def test_auto_decision_is_ignored_after_user_took_control() -> None:
    room = make_room(brightness=50, last_brightness=50)

    assert apply_auto_brightness(room, 10) == room


def test_circadian_decision_works_while_light_is_off() -> None:
    room = make_room(color_mode=ColorMode.CIRCADIAN, brightness=0)

    assert apply_circadian_color_temp(room, 3000).color_temp_k == 3000


def test_circadian_decision_is_ignored_in_manual_color_mode() -> None:
    room = make_room(color_temp_k=5000)

    assert apply_circadian_color_temp(room, 3000) == room


# ---------- Инвариант 12: энергия ----------


def test_energy_is_power_times_time_in_watt_hours() -> None:
    record = energy_record(make_lamp(room_id=1), power_w=36, dt=10, time=NOW)

    assert record.energy_wh == pytest.approx(0.1)
    assert (record.lamp_id, record.room_id, record.time) == (1, 1, NOW)


def test_energy_history_stays_with_previous_room() -> None:
    lamp = make_lamp(room_id=1)
    old = energy_record(lamp, power_w=10, dt=10, time=NOW)

    moved = bind_lamp(unbind_lamp(lamp), room_id=2)
    new = energy_record(moved, power_w=10, dt=10, time=NOW)

    assert old.room_id == 1
    assert new.room_id == 2
