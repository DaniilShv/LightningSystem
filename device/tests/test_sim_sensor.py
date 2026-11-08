from datetime import datetime, timedelta, timezone

import pytest

from lighting.hal import Clock, SensorError
from lighting.sim.light import VirtualLight
from lighting.sim.sensor import VirtualSensor, daylight_lux

TZ = timezone(timedelta(hours=5))
MIDDAY = datetime(2026, 11, 4, 12, 15, tzinfo=TZ)
NIGHT = datetime(2026, 11, 4, 0, 0, tzinfo=TZ)


class FixedClock(Clock):
    """Часы, которые двигаем руками."""

    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment

    def advance(self, seconds: float) -> None:
        self.moment += timedelta(seconds=seconds)


def test_daylight_is_zero_at_night() -> None:
    assert daylight_lux(NIGHT, window=1.0) == 0


def test_daylight_peaks_at_midday_and_scales_with_window() -> None:
    assert daylight_lux(MIDDAY, window=1.0) == 900
    assert daylight_lux(MIDDAY, window=0.5) == 450


def test_dark_lamp_adds_no_light() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=False, warm=1.0, cool=1.0)
    sensor = VirtualSensor(clock=FixedClock(NIGHT), window=1.0, lamps=[lamp])

    reading = sensor.read()

    assert reading.lux == 0
    assert reading.cct is None


def test_lamp_light_is_added_to_readings() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=True, warm=0.5, cool=0.5)
    sensor = VirtualSensor(
        clock=FixedClock(NIGHT), window=1.0, lamps=[lamp], lux_at_full=300
    )

    reading = sensor.read()

    assert reading.lux == 300
    assert reading.cct == 4600


def test_cct_mixes_daylight_and_lamp() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=True, warm=0.5, cool=0.5)
    sensor = VirtualSensor(
        clock=FixedClock(MIDDAY), window=1.0, lamps=[lamp], lux_at_full=300
    )

    reading = sensor.read()

    assert reading.lux == 1200
    assert reading.cct == 6025


def test_reading_fades_instead_of_jumping() -> None:
    clock = FixedClock(NIGHT)
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=True, warm=0.5, cool=0.5)
    sensor = VirtualSensor(clock=clock, window=0.0, lamps=[lamp], lux_at_full=300)

    assert sensor.read().lux == 300

    lamp.set_output(relay=False, warm=0.0, cool=0.0)
    clock.advance(0.5)

    assert sensor.read().lux == 150


def test_broken_wire_raises_until_repaired() -> None:
    sensor = VirtualSensor(clock=FixedClock(NIGHT), window=1.0)

    sensor.break_wire()
    with pytest.raises(SensorError):
        sensor.read()

    sensor.repair()
    assert sensor.read().lux == 0
