from dataclasses import dataclass
from datetime import datetime

from lighting.hal import Clock


@dataclass(frozen=True)
class DeviceInfo:
    name: str
    version: str
    runtime: str
    time: datetime


class SystemService:
    """Сведения об устройстве: имя, версия, режим запуска, время."""

    def __init__(self, clock: Clock, name: str, version: str, runtime: str) -> None:
        self._clock = clock
        self._name = name
        self._version = version
        self._runtime = runtime

    def info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._name,
            version=self._version,
            runtime=self._runtime,
            time=self._clock.now(),
        )
