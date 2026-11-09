from collections.abc import Mapping

from lighting.hal import PowerMeter
from lighting.sim.light import VirtualLight


class VirtualPowerMeter(PowerMeter):
    """Мощность по формуле из docs/model.md: P = max_power_w × duty."""

    def __init__(self, lamps: Mapping[int, VirtualLight]) -> None:
        self._lamps = dict(lamps)

    def power_by_lamp_w(self) -> dict[int, float]:
        return {lamp_id: lamp.power_w for lamp_id, lamp in self._lamps.items()}
