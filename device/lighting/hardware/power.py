from collections.abc import Sequence

from lighting.hal import PowerMeter
from lighting.hardware.light import GpioLight


class EstimatedPowerMeter(PowerMeter):
    """Мощность на Pi считается, а не измеряется.

    Формула из docs/model.md: P = max_power_w × duty. Настоящий датчик тока
    (INA219) — отдельная задача, команда её ещё не решала.
    """

    def __init__(self, lamps: Sequence[GpioLight]) -> None:
        self._lamps = list(lamps)

    def total_power_w(self) -> float:
        return sum(lamp.power_w for lamp in self._lamps)
