import pytest

from lighting.hardware.light import GpioLight
from lighting.hardware.power import EstimatedPowerMeter


def make_light(max_power_w: float, relay_pin: int = 17, warm_pin: int = 18, cool_pin: int = 19) -> GpioLight:
    return GpioLight(
        relay_pin=relay_pin,
        warm_pin=warm_pin,
        cool_pin=cool_pin,
        max_power_w=max_power_w,
    )


def test_reports_power_of_each_lamp() -> None:
    first = make_light(max_power_w=10.0)
    second = make_light(max_power_w=20.0, relay_pin=20, warm_pin=21, cool_pin=22)
    first.set_output(relay=True, warm=0.5, cool=0.5)
    second.set_output(relay=True, warm=0.25, cool=0.25)

    meter = EstimatedPowerMeter({1: first, 2: second})

    assert meter.power_by_lamp_w() == pytest.approx({1: 10.0, 2: 10.0})


def test_dark_lamps_use_no_power() -> None:
    lamp = make_light(max_power_w=10.0)

    meter = EstimatedPowerMeter({1: lamp})

    assert meter.power_by_lamp_w() == {1: 0.0}
