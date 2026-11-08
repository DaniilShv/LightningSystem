"""Виртуальное железо: физика света и мощности, ускорение времени (реализует hal).

Чистый модуль: без HTTP, базы данных и asyncio.
"""

from lighting.sim.clock import VirtualClock
from lighting.sim.light import VirtualLight
from lighting.sim.power import VirtualPowerMeter
from lighting.sim.sensor import VirtualSensor

__all__ = ["VirtualClock", "VirtualLight", "VirtualPowerMeter", "VirtualSensor"]
