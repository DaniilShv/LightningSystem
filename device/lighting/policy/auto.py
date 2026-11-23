"""Авто-режим: подобрать уставку яркости под целевую освещённость (docs/model.md, «Авто-режим»).

Регулятор работает по обратной связи: датчик видит и дневной свет, и свет самих ламп,
поэтому уставка меняется маленькими шагами, а каждый следующий шаг учитывает результат прошлого.
"""

from lighting.domain.entities import MAX_BRIGHTNESS, MIN_BRIGHTNESS

DEADBAND_SHARE = 0.1  # ±10 % от цели — свет не трогаем, чтобы он не дёргался от шума датчика
GAIN = 0.5  # какую долю ошибки (в процентах от цели) исправляем за один шаг
MAX_STEP = 10.0  # больше 10 % уставки за шаг не меняем: свет меняется спокойно


def auto_brightness(setpoint: float, lux: float, target_lux: float) -> float | None:
    """Новая уставка яркости по свежему замеру или None, если менять нечего.

    setpoint — текущая уставка комнаты 0..100, lux — замер датчика, target_lux — цель комнаты.
    """
    if target_lux <= 0:
        raise ValueError(f"Целевая освещённость должна быть больше нуля, получено {target_lux}")

    error = target_lux - lux
    if abs(error) <= DEADBAND_SHARE * target_lux:
        return None

    step = _clamp(GAIN * error / target_lux * 100, -MAX_STEP, MAX_STEP)
    new_setpoint = _clamp(setpoint + step, MIN_BRIGHTNESS, MAX_BRIGHTNESS)
    if new_setpoint == setpoint:
        return None
    return new_setpoint


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
