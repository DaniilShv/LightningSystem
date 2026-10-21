from datetime import datetime, timedelta, timezone

import pytest

from lighting.sim.clock import VirtualClock

TZ = timezone(timedelta(hours=5))
START = datetime(2026, 10, 20, 12, 0, tzinfo=TZ)


class FakeSource:
    """Реальное время, которое двигаем руками."""

    def __init__(self) -> None:
        self.value = START

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def source() -> FakeSource:
    return FakeSource()


def test_follows_real_time_by_default(source: FakeSource) -> None:
    clock = VirtualClock(source)
    source.advance(10)

    assert clock.now() == START + timedelta(seconds=10)


def test_set_time_rewinds(source: FakeSource) -> None:
    clock = VirtualClock(source)
    evening = datetime(2026, 10, 20, 19, 30, tzinfo=TZ)

    clock.set_time(evening)
    source.advance(60)

    assert clock.now() == evening + timedelta(seconds=60)


def test_speed_accelerates_without_jump(source: FakeSource) -> None:
    clock = VirtualClock(source)
    source.advance(10)

    clock.set_speed(600)
    assert clock.now() == START + timedelta(seconds=10)

    source.advance(1)
    assert clock.now() == START + timedelta(seconds=10 + 600)


def test_reset_returns_real_time_and_speed(source: FakeSource) -> None:
    clock = VirtualClock(source)
    clock.set_time(datetime(2026, 1, 1, tzinfo=TZ))
    clock.set_speed(60)

    clock.reset()
    source.advance(5)

    assert clock.speed == 1
    assert clock.now() == source.value


def test_speed_must_be_positive(source: FakeSource) -> None:
    with pytest.raises(ValueError):
        VirtualClock(source).set_speed(0)
