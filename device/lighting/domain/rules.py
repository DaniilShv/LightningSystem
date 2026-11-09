"""Правила из инвариантов docs/model.md.

Функции ничего не меняют: получают сущность и возвращают новую. Применяет и сохраняет результат service.
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime

from lighting.domain.entities import (
    ColorMode,
    EnergyRecord,
    Lamp,
    Mode,
    Room,
    Sensor,
    SensorStatus,
)

FAILED_READS_BEFORE_OFFLINE = 3
SECONDS_PER_HOUR = 3600


class RuleViolation(Exception):
    """Действие нарушает правило модели. В API превращается в ошибку 409."""


# ---------- Яркость ----------


def set_brightness(room: Room, brightness: float) -> Room:
    """Ручное изменение яркости: переводит комнату в manual (инвариант 9)."""
    last_brightness = brightness if brightness > 0 else room.last_brightness
    return replace(room, mode=Mode.MANUAL, brightness=brightness, last_brightness=last_brightness)


def turn_on(room: Room) -> Room:
    """«Включить» — вернуть последнюю ненулевую уставку (инвариант 6)."""
    return set_brightness(room, room.last_brightness)


def turn_off(room: Room) -> Room:
    """«Выключить» — уставка 0 (инвариант 6)."""
    return set_brightness(room, 0.0)


def set_mode(room: Room, mode: Mode, sensor: Sensor | None) -> Room:
    """Сменить режим яркости. sensor — датчик этой комнаты, если он есть (инвариант 7)."""
    if mode is Mode.AUTO and (
        sensor is None or sensor.room_id != room.id or sensor.status is not SensorStatus.ONLINE
    ):
        raise RuleViolation("Авто-режим невозможен: у комнаты нет датчика в статусе «онлайн»")
    return replace(room, mode=mode)


def apply_auto_brightness(room: Room, brightness: float) -> Room:
    """Применить решение авто-режима. Если пользователь уже перехватил управление, решение устарело."""
    if room.mode is not Mode.AUTO:
        return room
    last_brightness = brightness if brightness > 0 else room.last_brightness
    return replace(room, brightness=brightness, last_brightness=last_brightness)


def on_sensor_lost(room: Room) -> Room:
    """Датчик потерян или отвязан: режим manual, уставка остаётся, свет не скачет (инвариант 8)."""
    return replace(room, mode=Mode.MANUAL)


# ---------- Оттенок ----------


def set_color_temp(room: Room, color_temp_k: float) -> Room:
    """Ручное изменение оттенка: режим оттенка manual, режим яркости не трогаем (инвариант 9)."""
    return replace(room, color_mode=ColorMode.MANUAL, color_temp_k=color_temp_k)


def set_color_mode(room: Room, color_mode: ColorMode) -> Room:
    return replace(room, color_mode=color_mode)


def apply_circadian_color_temp(room: Room, color_temp_k: float) -> Room:
    """Применить решение циркадного режима. Работает и при выключенном свете."""
    if room.color_mode is not ColorMode.CIRCADIAN:
        return room
    return replace(room, color_temp_k=color_temp_k)


# ---------- Привязки ----------


def bind_lamp(lamp: Lamp, room_id: int) -> Lamp:
    """Лампа состоит максимум в одной комнате (инвариант 1)."""
    if lamp.room_id is not None and lamp.room_id != room_id:
        raise RuleViolation(f"Лампа «{lamp.name}» уже в другой комнате")
    return replace(lamp, room_id=room_id)


def unbind_lamp(lamp: Lamp) -> Lamp:
    """Отвязать лампу, в том числе при удалении комнаты: сама лампа остаётся в реестре (инвариант 3)."""
    return replace(lamp, room_id=None)


def bind_sensor(sensor: Sensor, room_id: int, all_sensors: Iterable[Sensor]) -> Sensor:
    """Датчик — максимум в одной комнате, у комнаты — максимум один датчик (инвариант 2)."""
    if sensor.room_id is not None and sensor.room_id != room_id:
        raise RuleViolation(f"Датчик «{sensor.name}» уже в другой комнате")
    if any(other.room_id == room_id and other.id != sensor.id for other in all_sensors):
        raise RuleViolation("У комнаты уже есть датчик")
    return replace(sensor, room_id=room_id)


def unbind_sensor(sensor: Sensor) -> Sensor:
    """Отвязать датчик, в том числе при удалении комнаты: сам датчик остаётся в реестре (инвариант 3)."""
    return replace(sensor, room_id=None)


# ---------- Датчик и энергия ----------


def record_reading(sensor: Sensor, lux: float, cct: int | None) -> Sensor:
    """Успешное чтение: датчик онлайн. В авто-режим комната сама не вернётся (инвариант 8)."""
    return replace(sensor, lux=lux, cct=cct, status=SensorStatus.ONLINE, failed_reads=0)


def record_failed_read(sensor: Sensor) -> Sensor:
    """Неудачное чтение: после 3 ошибок подряд датчик оффлайн и старым показаниям больше не верим."""
    failed_reads = sensor.failed_reads + 1
    if failed_reads < FAILED_READS_BEFORE_OFFLINE:
        return replace(sensor, failed_reads=failed_reads)
    return replace(sensor, failed_reads=failed_reads, status=SensorStatus.OFFLINE, lux=None, cct=None)


def energy_record(lamp: Lamp, power_w: float, dt: float, time: datetime) -> EnergyRecord:
    """Энергия за dt секунд. Комната запоминается сейчас, поэтому история не «переезжает» (инвариант 12)."""
    return EnergyRecord(
        time=time,
        lamp_id=lamp.id,
        room_id=lamp.room_id,
        energy_wh=power_w * dt / SECONDS_PER_HOUR,
    )
