"""Интерфейсы драйверов железа: LightDriver, SensorDriver, PowerMeter, Clock.

Остальной код видит только эти интерфейсы. Реализации — в sim (виртуальное железо)
и hardware (Raspberry Pi). Чистый модуль, ни от чего не зависит.
"""

from lighting.hal.clock import Clock

__all__ = ["Clock"]
