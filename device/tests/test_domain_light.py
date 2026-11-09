import pytest

from lighting.domain import Lamp, LampPins, Room, approach, channels, fade_lamp


def make_lamp(brightness: float = 0.0, color_temp_k: float = 2700) -> Lamp:
    return Lamp(
        id=1,
        name="Люстра",
        pins=LampPins(relay=5, warm=17, cool=27),
        max_power_w=24,
        room_id=1,
        brightness=brightness,
        color_temp_k=color_temp_k,
    )


def test_warmest_full_brightness_uses_only_warm_channel() -> None:
    result = channels(100, 2700)

    assert result.relay is True
    assert result.warm == pytest.approx(1.0)
    assert result.cool == pytest.approx(0.0)


def test_coolest_full_brightness_uses_only_cool_channel() -> None:
    result = channels(100, 6500)

    assert result.warm == pytest.approx(0.0)
    assert result.cool == pytest.approx(1.0)


def test_middle_temperature_splits_channels_equally() -> None:
    result = channels(100, 4600)

    assert result.warm == pytest.approx(0.5)
    assert result.cool == pytest.approx(0.5)


def test_half_brightness_is_about_22_percent_of_light() -> None:
    result = channels(50, 2700)

    assert result.warm + result.cool == pytest.approx(0.5**2.2)
    assert result.warm + result.cool == pytest.approx(0.22, abs=0.005)


def test_zero_brightness_opens_relay_and_darkens_channels() -> None:
    result = channels(0, 4000)

    assert result.relay is False
    assert result.warm == 0
    assert result.cool == 0


@pytest.mark.parametrize(("brightness", "color_temp_k"), [(-1, 4000), (101, 4000), (50, 2699), (50, 6501)])
def test_channels_reject_values_out_of_range(brightness: float, color_temp_k: float) -> None:
    with pytest.raises(ValueError):
        channels(brightness, color_temp_k)


def test_approach_moves_up_and_down_with_limited_speed() -> None:
    assert approach(0, 100, dt=0.1, speed=50) == 5
    assert approach(100, 0, dt=0.1, speed=50) == 95


def test_approach_does_not_overshoot_setpoint() -> None:
    assert approach(99, 100, dt=1, speed=50) == 100
    assert approach(1, 0, dt=1, speed=50) == 0


def test_approach_ignores_negative_dt() -> None:
    assert approach(30, 100, dt=-5, speed=50) == 30


def test_fade_covers_whole_brightness_range_in_fade_time() -> None:
    lamp = make_lamp(brightness=0)
    room = Room(id=1, name="Гостиная", brightness=100, color_temp_k=2700)

    halfway = fade_lamp(lamp, room, dt=0.3, fade_ms=600)
    finished = fade_lamp(halfway, room, dt=0.3, fade_ms=600)

    assert halfway.brightness == pytest.approx(50)
    assert finished.brightness == 100


def test_fade_covers_whole_temperature_range_in_fade_time() -> None:
    lamp = make_lamp(color_temp_k=2700)
    room = Room(id=1, name="Гостиная", color_temp_k=6500)

    halfway = fade_lamp(lamp, room, dt=0.3, fade_ms=600)
    finished = fade_lamp(halfway, room, dt=0.3, fade_ms=600)

    assert halfway.color_temp_k == pytest.approx(4600)
    assert finished.color_temp_k == 6500


def test_setpoint_and_actual_differ_during_fade() -> None:
    """Инвариант 10: уставка и фактическая яркость — разные величины."""
    room = Room(id=1, name="Гостиная", brightness=100)

    lamp = fade_lamp(make_lamp(), room, dt=0.03)

    assert 0 < lamp.brightness < room.brightness


def test_all_lamps_of_room_reach_room_setpoints() -> None:
    """Инвариант 4: все лампы комнаты получают яркость и цветовую температуру комнаты."""
    room = Room(id=1, name="Гостиная", brightness=62, color_temp_k=3500)
    lamps = [make_lamp(brightness=0, color_temp_k=2700), make_lamp(brightness=100, color_temp_k=6500)]

    for _ in range(100):
        lamps = [fade_lamp(lamp, room, dt=0.03) for lamp in lamps]

    assert [lamp.brightness for lamp in lamps] == [62, 62]
    assert [lamp.color_temp_k for lamp in lamps] == [3500, 3500]


def test_zero_fade_time_jumps_to_setpoint() -> None:
    room = Room(id=1, name="Гостиная", brightness=70, color_temp_k=5000)

    lamp = fade_lamp(make_lamp(), room, dt=0.03, fade_ms=0)

    assert (lamp.brightness, lamp.color_temp_k) == (70, 5000)


def test_relay_stays_closed_until_light_fades_out() -> None:
    """Реле размыкается, только когда ШИМ уже погас."""
    room = Room(id=1, name="Гостиная", brightness=0, color_temp_k=4000)
    lamp = make_lamp(brightness=100, color_temp_k=4000)

    while lamp.brightness > 0:
        result = channels(lamp.brightness, lamp.color_temp_k)
        assert result.relay is True
        lamp = fade_lamp(lamp, room, dt=0.03)

    assert channels(lamp.brightness, lamp.color_temp_k) == channels(0, 4000)


def test_relay_closes_with_first_fade_step() -> None:
    """При включении реле замыкается сразу."""
    room = Room(id=1, name="Гостиная", brightness=50)

    lamp = fade_lamp(make_lamp(), room, dt=0.03)

    assert channels(lamp.brightness, lamp.color_temp_k).relay is True
