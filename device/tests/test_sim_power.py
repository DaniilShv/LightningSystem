from lighting.sim.light import VirtualLight
from lighting.sim.power import VirtualPowerMeter


def test_reports_power_of_each_lamp() -> None:
    first = VirtualLight(max_power_w=10)
    second = VirtualLight(max_power_w=20)
    first.set_output(relay=True, warm=0.5, cool=0.5)
    second.set_output(relay=True, warm=0.25, cool=0.25)

    meter = VirtualPowerMeter({1: first, 2: second})

    # 10 Вт при полной доле света и 20 Вт при половине.
    assert meter.power_by_lamp_w() == {1: 10, 2: 10}


def test_dark_lamps_use_no_power() -> None:
    lamp = VirtualLight(max_power_w=10)
    lamp.set_output(relay=False, warm=1.0, cool=1.0)

    assert VirtualPowerMeter({1: lamp}).power_by_lamp_w() == {1: 0}
