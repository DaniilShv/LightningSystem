import pytest

from lighting.hardware.light import GpioLight


def make_light(max_power_w: float = 10.0) -> GpioLight:
    return GpioLight(relay_pin=17, warm_pin=18, cool_pin=19, max_power_w=max_power_w)


def test_applies_channels_and_counts_power() -> None:
    lamp = make_light()

    lamp.set_output(relay=True, warm=0.5, cool=0.25)

    assert lamp.relay_closed is True
    assert lamp.duty == pytest.approx(0.75)
    assert lamp.power_w == pytest.approx(7.5)


def test_open_relay_means_no_light_and_no_power() -> None:
    lamp = make_light()
    lamp.set_output(relay=True, warm=1.0, cool=0.0)

    lamp.set_output(relay=False, warm=1.0, cool=0.0)

    assert lamp.relay_closed is False
    assert lamp.duty == 0.0
    assert lamp.power_w == 0.0


def test_channels_are_clamped_to_range() -> None:
    lamp = make_light()

    lamp.set_output(relay=True, warm=2.0, cool=-1.0)

    assert lamp.duty == pytest.approx(1.0)


def test_close_turns_off_and_releases_pins() -> None:
    lamp = make_light()
    lamp.set_output(relay=True, warm=0.5, cool=0.5)

    lamp.close()

    assert lamp.closed is True
    # Повторная остановка не должна падать: цикл может вызвать её дважды.
    lamp.close()
