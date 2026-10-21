from collections.abc import Callable
from datetime import datetime

from lighting.hal import Clock


def _system_now() -> datetime:
    return datetime.now().astimezone()


class VirtualClock(Clock):
    """Виртуальные часы: их можно перемотать (утро, вечер) и ускорить (×60, ×600).

    Время идёт от «опорной точки»: now = virtual_start + (реальное прошедшее время) × speed.
    source — откуда брать реальное время; в тестах его подменяют.
    """

    def __init__(self, source: Callable[[], datetime] = _system_now) -> None:
        self._source = source
        self.reset()

    @property
    def speed(self) -> float:
        return self._speed

    def now(self) -> datetime:
        elapsed = self._source() - self._real_start
        return self._virtual_start + elapsed * self._speed

    def set_time(self, moment: datetime) -> None:
        """Перемотать на заданный момент, скорость сохраняется."""
        self._anchor(moment, self._speed)

    def set_speed(self, speed: float) -> None:
        """Изменить скорость, не сдвигая текущее виртуальное время."""
        if speed <= 0:
            raise ValueError("Скорость времени должна быть больше нуля")
        self._anchor(self.now(), speed)

    def reset(self) -> None:
        """Вернуть реальное время и скорость ×1."""
        self._anchor(self._source(), 1.0)

    def _anchor(self, virtual_start: datetime, speed: float) -> None:
        self._real_start = self._source()
        self._virtual_start = virtual_start
        self._speed = speed
