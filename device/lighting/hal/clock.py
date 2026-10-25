from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Источник времени. Логика берёт время только отсюда, чтобы его можно было подменить и ускорить."""

    @abstractmethod
    def now(self) -> datetime:
        """Текущее время с часовым поясом устройства."""
