import pytest

from lighting.policy import auto_brightness


def test_inside_deadband_nothing_changes() -> None:
    # ±10 % от цели 300 — это 270..330 lux.
    assert auto_brightness(50, lux=300, target_lux=300) is None
    assert auto_brightness(50, lux=270, target_lux=300) is None
    assert auto_brightness(50, lux=330, target_lux=300) is None


def test_just_outside_deadband_makes_a_step() -> None:
    assert auto_brightness(50, lux=269, target_lux=300) is not None
    assert auto_brightness(50, lux=331, target_lux=300) is not None


def test_step_is_proportional_to_error() -> None:
    # error = 300 - 240 = 60 → 0.5 * 60 / 300 * 100 = 10... берём ошибку поменьше: 300 - 252 = 48 → 8.
    assert auto_brightness(50, lux=252, target_lux=300) == pytest.approx(58)
    assert auto_brightness(50, lux=348, target_lux=300) == pytest.approx(42)


def test_step_is_limited_to_ten_percent() -> None:
    assert auto_brightness(50, lux=0, target_lux=300) == 60
    assert auto_brightness(50, lux=3000, target_lux=300) == 40


def test_setpoint_stays_in_range() -> None:
    assert auto_brightness(95, lux=0, target_lux=300) == 100
    assert auto_brightness(5, lux=900, target_lux=300) == 0


def test_no_change_when_already_at_the_limit() -> None:
    """Темно, а свет уже на 100 % (или светло, а свет выключен) — менять нечего."""
    assert auto_brightness(100, lux=50, target_lux=300) is None
    assert auto_brightness(0, lux=900, target_lux=300) is None


def test_bright_daylight_turns_light_off_step_by_step() -> None:
    setpoint = 60.0
    steps = 0
    while (new := auto_brightness(setpoint, lux=900, target_lux=300)) is not None:
        setpoint, steps = new, steps + 1

    assert setpoint == 0
    assert steps == 6


def test_zero_target_is_rejected() -> None:
    with pytest.raises(ValueError):
        auto_brightness(50, lux=100, target_lux=0)
