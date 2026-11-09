from dataclasses import dataclass, replace

from lighting.domain.entities import (
    MAX_BRIGHTNESS,
    MAX_COLOR_TEMP_K,
    MIN_BRIGHTNESS,
    MIN_COLOR_TEMP_K,
    Lamp,
    Room,
    check_brightness,
    check_color_temp,
)

GAMMA = 2.2
DEFAULT_FADE_MS = 600


@dataclass(frozen=True)
class Channels:
    """Что подать на лампу: реле и доли ШИМ (доля времени «включено») тёплого и холодного канала, 0..1."""

    relay: bool
    warm: float
    cool: float


def channels(brightness: float, color_temp_k: float) -> Channels:
    """Перевести яркость и цветовую температуру в сигналы для LightDriver.

    Яркость в интерфейсе воспринимаемая, а на ножки идёт физическая доля света:
    глаз видит яркость нелинейно, поэтому нужна гамма-коррекция.
    """
    check_brightness(brightness)
    check_color_temp(color_temp_k)
    duty = (brightness / MAX_BRIGHTNESS) ** GAMMA
    cool_share = (color_temp_k - MIN_COLOR_TEMP_K) / (MAX_COLOR_TEMP_K - MIN_COLOR_TEMP_K)
    return Channels(
        relay=brightness > 0,
        warm=(1 - cool_share) * duty,
        cool=cool_share * duty,
    )


def approach(actual: float, setpoint: float, dt: float, speed: float) -> float:
    """Сдвинуть actual к setpoint не больше чем на speed × dt, не проскакивая уставку.

    dt — секунды, speed — единицы в секунду. Отрицательный dt бывает, когда
    виртуальные часы перемотали назад: тогда значение не меняется.
    """
    step = speed * max(dt, 0.0)
    if abs(setpoint - actual) <= step:
        return setpoint
    return actual + step if setpoint > actual else actual - step


def fade_lamp(lamp: Lamp, room: Room, dt: float, fade_ms: float = DEFAULT_FADE_MS) -> Lamp:
    """Один шаг плавного перехода: фактические значения лампы догоняют уставки комнаты.

    Весь диапазон яркости и весь диапазон температуры проходятся за fade_ms.
    fade_ms = 0 — без перехода, сразу к уставке.
    """
    if fade_ms <= 0:
        return replace(lamp, brightness=room.brightness, color_temp_k=room.color_temp_k)

    fade_s = fade_ms / 1000
    brightness_speed = (MAX_BRIGHTNESS - MIN_BRIGHTNESS) / fade_s
    color_temp_speed = (MAX_COLOR_TEMP_K - MIN_COLOR_TEMP_K) / fade_s
    return replace(
        lamp,
        brightness=approach(lamp.brightness, room.brightness, dt, brightness_speed),
        color_temp_k=approach(lamp.color_temp_k, room.color_temp_k, dt, color_temp_speed),
    )
