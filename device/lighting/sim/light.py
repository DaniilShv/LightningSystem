from lighting.hal import LightDriver

MIN_KELVIN = 2700
MAX_KELVIN = 6500


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class VirtualLight(LightDriver):
    """Виртуальная лампа: хранит каналы, из которых считаются свет и мощность."""

    def __init__(self, max_power_w: float, lux_at_full: float = 300.0) -> None:
        self._max_power_w = max_power_w
        self._lux_at_full = lux_at_full
        self._relay = False
        self._warm = 0.0
        self._cool = 0.0

    def set_output(self, relay: bool, warm: float, cool: float) -> None:
        self._relay = relay
        self._warm = _clamp01(warm)
        self._cool = _clamp01(cool)

    def close(self) -> None:
        """Ножек у виртуальной лампы нет, поэтому достаточно её погасить."""
        self.set_output(relay=False, warm=0.0, cool=0.0)

    @property
    def duty(self) -> float:
        """Физическая доля света 0..1, которую лампа даёт прямо сейчас."""
        if not self._relay:
            return 0.0
        return min(1.0, self._warm + self._cool)

    @property
    def kelvin(self) -> int | None:
        """Цветовая температура по соотношению каналов; None, если лампа не светит."""
        total = self._warm + self._cool
        if not self._relay or total == 0:
            return None
        warm_share = self._warm / total
        return round(MAX_KELVIN - (MAX_KELVIN - MIN_KELVIN) * warm_share)

    @property
    def lux(self) -> float:
        """Вклад в показания датчика комнаты: E = lux_at_full × duty (docs/model.md)."""
        return self._lux_at_full * self.duty

    @property
    def power_w(self) -> float:
        """Мощность считается от duty, а не от воспринимаемой яркости (docs/model.md)."""
        return self._max_power_w * self.duty
