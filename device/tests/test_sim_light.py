from lighting.sim.light import VirtualLight


def test_dark_until_relay_closes() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=False, warm=1.0, cool=1.0)

    assert lamp.duty == 0
    assert lamp.power_w == 0
    assert lamp.kelvin is None


def test_duty_is_sum_of_channels() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=True, warm=0.25, cool=0.25)

    assert lamp.duty == 0.5
    assert lamp.power_w == 5


def test_channels_are_clamped_to_unit_range() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=True, warm=2.0, cool=-1.0)

    assert lamp.duty == 1.0
    assert lamp.power_w == 10


def test_kelvin_follows_channel_ratio() -> None:
    lamp = VirtualLight(max_power_w=10)

    lamp.set_output(relay=True, warm=1.0, cool=0.0)
    assert lamp.kelvin == 2700

    lamp.set_output(relay=True, warm=0.0, cool=1.0)
    assert lamp.kelvin == 6500

    lamp.set_output(relay=True, warm=0.5, cool=0.5)
    assert lamp.kelvin == 4600
