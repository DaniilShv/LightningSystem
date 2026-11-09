from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

MIN_BRIGHTNESS = 0.0
MAX_BRIGHTNESS = 100.0
MIN_COLOR_TEMP_K = 2700
MAX_COLOR_TEMP_K = 6500

DEFAULT_TARGET_LUX = 300.0
DEFAULT_COLOR_TEMP_K = 4000


class Mode(StrEnum):
    """Кто управляет яркостью комнаты."""

    MANUAL = "manual"
    AUTO = "auto"


class ColorMode(StrEnum):
    """Кто управляет оттенком комнаты."""

    MANUAL = "manual"
    CIRCADIAN = "circadian"


class SensorStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


def check_brightness(value: float) -> None:
    if not MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS:
        raise ValueError(f"Яркость должна быть от 0 до 100, получено {value}")


def check_color_temp(value: float) -> None:
    if not MIN_COLOR_TEMP_K <= value <= MAX_COLOR_TEMP_K:
        raise ValueError(f"Цветовая температура должна быть от 2700 до 6500 K, получено {value}")


@dataclass(frozen=True)
class CurvePoint:
    """Опорная точка циркадной кривой: время суток в часах и цветовая температура."""

    hour: float
    color_temp_k: int


DEFAULT_CIRCADIAN_CURVE = (
    CurvePoint(0, 2700),
    CurvePoint(6, 2700),
    CurvePoint(9, 5000),
    CurvePoint(13, 6000),
    CurvePoint(17, 5000),
    CurvePoint(20, 3500),
    CurvePoint(22, 2700),
)


@dataclass(frozen=True)
class Site:
    """Объект: квартира или офис. Одно устройство управляет одним объектом."""

    name: str
    tariff_rub_per_kwh: float
    circadian_curve: tuple[CurvePoint, ...] = DEFAULT_CIRCADIAN_CURVE


@dataclass(frozen=True)
class Room:
    """Комната — единица управления. Здесь лежат уставки: то, что должно быть.

    Что есть на самом деле, хранит лампа (Lamp.brightness, Lamp.color_temp_k).
    last_brightness — последняя ненулевая уставка, к ней возвращается «Включить».
    """

    id: int
    name: str
    target_lux: float = DEFAULT_TARGET_LUX
    mode: Mode = Mode.MANUAL
    brightness: float = 0.0
    last_brightness: float = MAX_BRIGHTNESS
    color_mode: ColorMode = ColorMode.MANUAL
    color_temp_k: float = DEFAULT_COLOR_TEMP_K

    def __post_init__(self) -> None:
        check_brightness(self.brightness)
        check_brightness(self.last_brightness)
        check_color_temp(self.color_temp_k)
        if self.last_brightness == 0:
            raise ValueError("Последняя уставка не может быть нулевой")
        if self.target_lux <= 0:
            raise ValueError(f"Целевая освещённость должна быть больше нуля, получено {self.target_lux}")


@dataclass(frozen=True)
class LampPins:
    """Ножки GPIO лампы в нумерации BCM."""

    relay: int
    warm: int
    cool: int


@dataclass(frozen=True)
class Lamp:
    """CCT-лента. brightness и color_temp_k — фактические значения, они плавно догоняют уставку комнаты."""

    id: int
    name: str
    pins: LampPins
    max_power_w: float
    room_id: int | None = None
    brightness: float = 0.0
    color_temp_k: float = DEFAULT_COLOR_TEMP_K

    def __post_init__(self) -> None:
        check_brightness(self.brightness)
        check_color_temp(self.color_temp_k)


@dataclass(frozen=True)
class SensorConnection:
    """Как датчик подключён. mux_channel — канал мультиплексора, None — датчик подключён напрямую."""

    bus: str
    address: int
    mux_channel: int | None = None


@dataclass(frozen=True)
class Sensor:
    """Датчик TCS34725. Пока устройство не прочитало его ни разу, он считается оффлайн."""

    id: int
    name: str
    connection: SensorConnection
    room_id: int | None = None
    lux: float | None = None
    cct: int | None = None
    status: SensorStatus = SensorStatus.OFFLINE
    failed_reads: int = 0


@dataclass(frozen=True)
class Measurement:
    """Замер для истории."""

    time: datetime
    sensor_id: int
    room_id: int | None
    lux: float
    cct: int | None


@dataclass(frozen=True)
class EnergyRecord:
    """Энергия лампы за интервал. room_id — комната на момент замера и больше не меняется."""

    time: datetime
    lamp_id: int
    room_id: int | None
    energy_wh: float
