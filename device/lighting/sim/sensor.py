import random
from collections.abc import Sequence
from datetime import datetime

from lighting.hal import Clock, SensorDriver, SensorError, SensorReading
from lighting.sim.light import VirtualLight

DAY_PEAK_LUX = 900.0
DAY_CCT = 6500
DAWN_MINUTES = 7 * 60
DUSK_MINUTES = 17 * 60 + 30
INERTIA_SECONDS = 1.0
MIN_LUX_FOR_CCT = 1.0


def daylight_lux(moment: datetime, window: float) -> float:
    """Сколько уличного света попадает в комнату.

    Кривая из docs/model.md: рассвет около 7:00, закат около 17:30, максимум
    900 lux у окна. В комнату проходит доля window (0..1).
    """
    minutes = moment.hour * 60 + moment.minute + moment.second / 60
    if minutes <= DAWN_MINUTES or minutes >= DUSK_MINUTES:
        return 0.0
    peak = (DAWN_MINUTES + DUSK_MINUTES) / 2
    if minutes <= peak:
        share = (minutes - DAWN_MINUTES) / (peak - DAWN_MINUTES)
    else:
        share = (DUSK_MINUTES - minutes) / (DUSK_MINUTES - peak)
    return DAY_PEAK_LUX * share * window


class VirtualSensor(SensorDriver):
    """Виртуальный TCS34725 комнаты: уличный свет через окно плюс вклад ламп.

    Датчик не различает источники, как и настоящий: он складывает всё, что
    попадает в комнату. Показания слегка запаздывают — инерция около секунды.
    """

    def __init__(
        self,
        clock: Clock,
        window: float,
        lamps: Sequence[VirtualLight] = (),
        noise: float = 0.0,
        rng: random.Random | None = None,
    ) -> None:
        self._clock = clock
        self._window = window
        self._lamps = list(lamps)
        self._noise = noise
        self._rng = rng or random.Random(0)
        self._broken = False
        self._measured_lux: float | None = None
        self._last_read_at: datetime | None = None

    def break_wire(self) -> None:
        """Сымитировать обрыв: следующие чтения бросают ошибку, как настоящий smbus2."""
        self._broken = True

    def repair(self) -> None:
        self._broken = False

    def read(self) -> SensorReading:
        if self._broken:
            raise SensorError("Датчик не отвечает: обрыв провода")

        now = self._clock.now()
        sources = self._sources(now)
        lux = sum(value for value, _ in sources)
        measured = self._with_inertia(lux, now)
        if self._noise:
            measured *= 1 + self._rng.uniform(-self._noise, self._noise)
        return SensorReading(lux=round(measured, 1), cct=self._mixed_cct(sources, lux))

    def _sources(self, now: datetime) -> list[tuple[float, int]]:
        """Вклады в освещённость: (lux, цветовая температура источника)."""
        sources: list[tuple[float, int]] = []
        daylight = daylight_lux(now, self._window)
        if daylight > 0:
            sources.append((daylight, DAY_CCT))
        for lamp in self._lamps:
            lamp_kelvin = lamp.kelvin
            if lamp_kelvin is None:
                continue
            sources.append((lamp.lux, lamp_kelvin))
        return sources

    def _with_inertia(self, lux: float, now: datetime) -> float:
        if self._measured_lux is None or self._last_read_at is None:
            self._measured_lux = lux
            self._last_read_at = now
            return lux
        seconds = (now - self._last_read_at).total_seconds()
        self._last_read_at = now
        if seconds <= 0:
            return self._measured_lux
        share = min(1.0, seconds / INERTIA_SECONDS)
        self._measured_lux += (lux - self._measured_lux) * share
        return self._measured_lux

    @staticmethod
    def _mixed_cct(sources: list[tuple[float, int]], lux: float) -> int | None:
        if lux < MIN_LUX_FOR_CCT:
            return None
        weighted = sum(value * cct for value, cct in sources)
        return round(weighted / lux)
