from abc import ABC, abstractmethod
from dataclasses import dataclass


class SensorError(Exception):
    """Датчик не ответил: обрыв провода или ошибка на шине I2C."""


@dataclass(frozen=True)
class SensorReading:
    """Показания датчика: освещённость и цветовая температура."""

    lux: float
    # Оттенок не определить, если света слишком мало (в модели — lux < 1).
    cct: int | None


class SensorDriver(ABC):
    """Драйвер датчика освещённости TCS34725."""

    @abstractmethod
    def read(self) -> SensorReading:
        """Прочитать показания. При обрыве связи бросает SensorError."""
