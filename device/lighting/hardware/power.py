from collections.abc import Mapping

from lighting.hal import PowerMeter
from lighting.hardware.light import GpioLight


class EstimatedPowerMeter(PowerMeter):
    """Мощность на Pi считается, а не измеряется.

    Формула из docs/model.md: P = max_power_w × duty. Настоящий датчик тока
    (INA219) — отдельная задача, команда её ещё не решала.
    """

    def __init__(self, lamps: Mapping[int, GpioLight]) -> None:
        self._lamps = dict(lamps)

    def power_by_lamp_w(self) -> dict[int, float]:
        return {lamp_id: lamp.power_w for lamp_id, lamp in self._lamps.items()}
