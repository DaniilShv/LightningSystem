"""Интерфейсы драйверов железа: LightDriver, SensorDriver, PowerMeter, Clock.

Остальной код видит только эти интерфейсы. Реализации — в sim (виртуальное железо)
и hardware (Raspberry Pi). Чистый модуль, ни от чего не зависит.
"""

from lighting.hal.clock import Clock
from lighting.hal.light import LightDriver
from lighting.hal.power import PowerMeter
from lighting.hal.sensor import SensorDriver, SensorError, SensorReading

__all__ = ["Clock", "LightDriver", "PowerMeter", "SensorDriver", "SensorError", "SensorReading"]
