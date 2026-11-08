from lighting.sim.light import VirtualLight
from lighting.sim.power import VirtualPowerMeter


def test_meter_sums_all_lamps() -> None:
    first = VirtualLight(max_power_w=10)
    second = VirtualLight(max_power_w=20)
    first.set_output(relay=True, warm=0.5, cool=0.5)
    second.set_output(relay=True, warm=0.25, cool=0.25)

    meter = VirtualPowerMeter([first, second])

    # 10 Вт при полной доле света и 20 Вт при половине.
    assert meter.total_power_w() == 20


def test_dark_lamps_use_no_power() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=False, warm=1.0, cool=1.0)

    assert VirtualPowerMeter([lamp]).total_power_w() == 0
