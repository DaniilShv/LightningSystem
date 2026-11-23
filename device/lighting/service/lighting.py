import threading
from collections.abc import Mapping
from dataclasses import dataclass, replace

from lighting.domain import (
    ColorMode,
    Lamp,
    Mode,
    Room,
    Sensor,
    SensorStatus,
    Site,
    apply_auto_brightness,
    bind_lamp,
    bind_sensor,
    channels,
    fade_lamp,
    on_sensor_lost,
    record_failed_read,
    record_reading,
    set_brightness,
    set_color_mode,
    set_color_temp,
    set_mode,
    turn_off,
    turn_on,
    unbind_lamp,
    unbind_sensor,
)
from lighting.domain.entities import DEFAULT_TARGET_LUX
from lighting.domain.light import DEFAULT_FADE_MS
from lighting.hal import LightDriver, PowerMeter
from lighting.policy import auto_brightness
from lighting.service.errors import NotFoundError
from lighting.storage import Database


@dataclass(frozen=True)
class LampState:
    lamp: Lamp
    power_w: float


@dataclass(frozen=True)
class RoomState:
    """Комната вместе с тем, что к ней привязано: так её отдаёт API."""

    room: Room
    sensor: Sensor | None
    lamps: list[LampState]

    @property
    def power_w(self) -> float:
        return sum(lamp.power_w for lamp in self.lamps)


class LightingService:
    """Единственное место, где меняется состояние комнат, ламп и датчиков.

    Каждое изменение: взять замок → применить правило из domain → сохранить в базу → заменить в памяти.
    Замок нужен, потому что запросы API идут в пуле потоков, а цикл вывода на лампы — в asyncio.
    """

    def __init__(
        self,
        database: Database,
        lights: Mapping[int, LightDriver],
        power_meter: PowerMeter,
        fade_ms: float = DEFAULT_FADE_MS,
    ) -> None:
        self._database = database
        self._lights = dict(lights)
        self._power_meter = power_meter
        self._fade_ms = fade_ms
        self._lock = threading.Lock()
        self._site = database.load_site()
        self._rooms = {room.id: room for room in database.load_rooms()}
        self._lamps = {lamp.id: lamp for lamp in database.load_lamps()}
        self._sensors = {sensor.id: sensor for sensor in database.load_sensors()}
        # Первый шаг цикла выводит состояние на все лампы, дальше — только изменившиеся.
        self._outputs_applied = False

    # ---------- Комнаты ----------

    def list_rooms(self) -> list[RoomState]:
        with self._lock:
            return [self._room_state(room) for room in self._rooms.values()]

    def get_room(self, room_id: int) -> RoomState:
        with self._lock:
            return self._room_state(self._room(room_id))

    def create_room(self, name: str, target_lux: float | None = None) -> RoomState:
        with self._lock:
            room = self._database.insert_room(name, target_lux if target_lux is not None else DEFAULT_TARGET_LUX)
            self._rooms[room.id] = room
            return self._room_state(room)

    def update_room(self, room_id: int, name: str | None = None, target_lux: float | None = None) -> RoomState:
        with self._lock:
            room = self._room(room_id)
            room = replace(
                room,
                name=name if name is not None else room.name,
                target_lux=target_lux if target_lux is not None else room.target_lux,
            )
            return self._save_room(room)

    def delete_room(self, room_id: int) -> None:
        """Лампы и датчик комнаты не удаляются, а отвязываются (инвариант 3) — лампы гаснут сами (инвариант 13)."""
        with self._lock:
            self._room(room_id)
            self._database.delete_room(room_id)
            del self._rooms[room_id]
            for lamp in self._lamps_of(room_id):
                self._lamps[lamp.id] = unbind_lamp(lamp)
            sensor = self._sensor_of(room_id)
            if sensor is not None:
                self._sensors[sensor.id] = unbind_sensor(sensor)

    def control(
        self,
        room_id: int,
        mode: str | None = None,
        brightness: float | None = None,
        color_mode: str | None = None,
        color_temp_k: float | None = None,
    ) -> RoomState:
        """Сначала значения, потом режимы: {brightness: 40, mode: "auto"} — авто, начиная с 40 %."""
        with self._lock:
            room = self._room(room_id)
            if brightness is not None:
                room = set_brightness(room, brightness)
            if color_temp_k is not None:
                room = set_color_temp(room, color_temp_k)
            if mode is not None:
                room = set_mode(room, Mode(mode), self._sensor_of(room_id))
            if color_mode is not None:
                room = set_color_mode(room, ColorMode(color_mode))
            return self._save_room(room)

    def power(self, room_id: int, on: bool) -> RoomState:
        with self._lock:
            room = self._room(room_id)
            return self._save_room(turn_on(room) if on else turn_off(room))

    # ---------- Привязки ----------

    def bind_lamp(self, room_id: int, lamp_id: int) -> RoomState:
        with self._lock:
            room = self._room(room_id)
            lamp = bind_lamp(self._lamp(lamp_id), room_id)
            self._database.save_lamp(lamp)
            self._lamps[lamp.id] = lamp
            return self._room_state(room)

    def unbind_lamp(self, room_id: int, lamp_id: int) -> RoomState:
        with self._lock:
            room = self._room(room_id)
            lamp = self._lamp(lamp_id)
            if lamp.room_id != room_id:
                raise NotFoundError(f"Лампа «{lamp.name}» не привязана к комнате «{room.name}»")
            lamp = unbind_lamp(lamp)
            self._database.save_lamp(lamp)
            self._lamps[lamp.id] = lamp
            return self._room_state(room)

    def bind_sensor(self, room_id: int, sensor_id: int) -> RoomState:
        with self._lock:
            room = self._room(room_id)
            sensor = bind_sensor(self._sensor(sensor_id), room_id, self._sensors.values())
            self._database.save_sensor(sensor)
            self._sensors[sensor.id] = sensor
            return self._room_state(room)

    def unbind_sensor(self, room_id: int, sensor_id: int) -> RoomState:
        """Без датчика авто-режим невозможен (инвариант 7), поэтому комната переходит в manual."""
        with self._lock:
            room = self._room(room_id)
            sensor = self._sensor(sensor_id)
            if sensor.room_id != room_id:
                raise NotFoundError(f"Датчик «{sensor.name}» не привязан к комнате «{room.name}»")
            sensor = unbind_sensor(sensor)
            self._database.save_sensor(sensor)
            self._sensors[sensor.id] = sensor
            return self._save_room(on_sensor_lost(room))

    # ---------- Реестры и объект ----------

    def list_lamps(self, free: bool = False) -> list[LampState]:
        with self._lock:
            power = self._power_meter.power_by_lamp_w()
            return [
                LampState(lamp, power.get(lamp.id, 0.0))
                for lamp in self._lamps.values()
                if not free or lamp.room_id is None
            ]

    def rename_lamp(self, lamp_id: int, name: str) -> LampState:
        with self._lock:
            lamp = replace(self._lamp(lamp_id), name=name)
            self._database.save_lamp(lamp)
            self._lamps[lamp.id] = lamp
            return LampState(lamp, self._power_meter.power_by_lamp_w().get(lamp.id, 0.0))

    def list_sensors(self, free: bool = False) -> list[Sensor]:
        with self._lock:
            return [sensor for sensor in self._sensors.values() if not free or sensor.room_id is None]

    def rename_sensor(self, sensor_id: int, name: str) -> Sensor:
        with self._lock:
            sensor = replace(self._sensor(sensor_id), name=name)
            self._database.save_sensor(sensor)
            self._sensors[sensor.id] = sensor
            return sensor

    def get_site(self) -> Site:
        with self._lock:
            return self._site

    def update_site(self, name: str | None = None, tariff_rub_per_kwh: float | None = None) -> Site:
        with self._lock:
            site = replace(
                self._site,
                name=name if name is not None else self._site.name,
                tariff_rub_per_kwh=tariff_rub_per_kwh if tariff_rub_per_kwh is not None else self._site.tariff_rub_per_kwh,
            )
            self._database.save_site(site)
            self._site = site
            return site

    # ---------- Замеры датчиков и авто-режим ----------
    # Эти два метода вызывает цикл опроса датчиков (telemetry) после каждого чтения.

    def record_sensor_reading(self, sensor_id: int, lux: float, cct: int | None) -> Sensor:
        """Датчик ответил: обновить показания и, если комната в авто, применить решение регулятора."""
        with self._lock:
            sensor = record_reading(self._sensor(sensor_id), lux, cct)
            self._sensors[sensor.id] = sensor
            room = self._rooms.get(sensor.room_id) if sensor.room_id is not None else None
            if room is not None and room.mode is Mode.AUTO and self._lamps_settled(room):
                new_setpoint = auto_brightness(room.brightness, lux, room.target_lux)
                if new_setpoint is not None:
                    self._save_room(apply_auto_brightness(room, new_setpoint))
            return sensor

    def record_sensor_failure(self, sensor_id: int) -> Sensor:
        """Датчик не ответил. После 3 ошибок подряд он оффлайн, и комната переходит в manual (инвариант 8)."""
        with self._lock:
            sensor = record_failed_read(self._sensor(sensor_id))
            self._sensors[sensor.id] = sensor
            room = self._rooms.get(sensor.room_id) if sensor.room_id is not None else None
            if room is not None and room.mode is Mode.AUTO and sensor.status is SensorStatus.OFFLINE:
                self._save_room(on_sensor_lost(room))
            return sensor

    # ---------- Цикл вывода ----------

    def tick(self, dt: float) -> None:
        """Шаг цикла вывода: фактические значения ламп догоняют уставки, результат идёт на ножки."""
        with self._lock:
            for lamp in list(self._lamps.values()):
                room = self._rooms.get(lamp.room_id) if lamp.room_id is not None else None
                faded = fade_lamp(lamp, room, dt, self._fade_ms)
                if faded == lamp and self._outputs_applied:
                    continue
                self._lamps[lamp.id] = faded
                light = self._lights.get(lamp.id)
                if light is not None:
                    output = channels(faded.brightness, faded.color_temp_k)
                    light.set_output(output.relay, output.warm, output.cool)
            self._outputs_applied = True

    def close(self) -> None:
        """Погасить все лампы и освободить ножки: вызывается при остановке устройства."""
        with self._lock:
            for light in self._lights.values():
                light.close()

    # ---------- Внутреннее ----------

    def _room(self, room_id: int) -> Room:
        if room_id not in self._rooms:
            raise NotFoundError(f"Комнаты {room_id} нет")
        return self._rooms[room_id]

    def _lamp(self, lamp_id: int) -> Lamp:
        if lamp_id not in self._lamps:
            raise NotFoundError(f"Лампы {lamp_id} нет")
        return self._lamps[lamp_id]

    def _sensor(self, sensor_id: int) -> Sensor:
        if sensor_id not in self._sensors:
            raise NotFoundError(f"Датчика {sensor_id} нет")
        return self._sensors[sensor_id]

    def _lamps_of(self, room_id: int) -> list[Lamp]:
        return [lamp for lamp in self._lamps.values() if lamp.room_id == room_id]

    def _sensor_of(self, room_id: int) -> Sensor | None:
        return next((sensor for sensor in self._sensors.values() if sensor.room_id == room_id), None)

    def _lamps_settled(self, room: Room) -> bool:
        """Лампы дошли до уставки: только тогда замер показывает результат прошлого шага регулятора."""
        return all(lamp.brightness == room.brightness for lamp in self._lamps_of(room.id))

    def _save_room(self, room: Room) -> RoomState:
        self._database.save_room(room)
        self._rooms[room.id] = room
        return self._room_state(room)

    def _room_state(self, room: Room) -> RoomState:
        power = self._power_meter.power_by_lamp_w()
        return RoomState(
            room=room,
            sensor=self._sensor_of(room.id),
            lamps=[LampState(lamp, power.get(lamp.id, 0.0)) for lamp in self._lamps_of(room.id)],
        )
