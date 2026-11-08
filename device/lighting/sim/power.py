from collections.abc import Sequence

from lighting.hal import PowerMeter
from lighting.sim.light import VirtualLight


class VirtualPowerMeter(PowerMeter):
    """Мощность по формуле из docs/model.md: P = max_power_w × duty."""

    def __init__(self, lamps: Sequence[VirtualLight]) -> None:
        self._lamps = list(lamps)

    def total_power_w(self) -> float:
        return sum(lamp.power_w for lamp in self._lamps)
