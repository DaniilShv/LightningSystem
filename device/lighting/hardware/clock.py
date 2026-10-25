from datetime import datetime

from lighting.hal import Clock


class SystemClock(Clock):
    """Системные часы Raspberry Pi."""

    def now(self) -> datetime:
        return datetime.now().astimezone()
