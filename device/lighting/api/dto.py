from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lighting.service.lighting import LampState, RoomState, Sensor

# Ограничения полей: неверные значения FastAPI отклоняет с кодом 422 ещё до вызова service.
Name = Annotated[str, Field(min_length=1, max_length=50)]
Brightness = Annotated[float, Field(ge=0, le=100)]
ColorTempK = Annotated[float, Field(ge=2700, le=6500)]
TargetLux = Annotated[float, Field(gt=0)]
Tariff = Annotated[float, Field(ge=0)]


class ErrorOut(BaseModel):
    detail: str


class HealthOut(BaseModel):
    name: str
    version: str
    runtime: Literal["virtual", "hardware"]
    time: datetime


class AuthCheckOut(BaseModel):
    ok: bool


# ---------- Объект ----------


class SiteOut(BaseModel):
    name: str
    tariff_rub_per_kwh: float


class SiteUpdate(BaseModel):
    name: Name | None = None
    tariff_rub_per_kwh: Tariff | None = None


# ---------- Лампы и датчики ----------


class LampOut(BaseModel):
    id: int
    name: str
    room_id: int | None
    brightness: float
    color_temp_k: float
    power_w: float

    @classmethod
    def from_state(cls, state: LampState) -> "LampOut":
        lamp = state.lamp
        return cls(
            id=lamp.id,
            name=lamp.name,
            room_id=lamp.room_id,
            brightness=lamp.brightness,
            color_temp_k=lamp.color_temp_k,
            power_w=state.power_w,
        )


class RoomLampOut(BaseModel):
    id: int
    name: str
    brightness: float
    color_temp_k: float
    power_w: float


class SensorOut(BaseModel):
    id: int
    name: str
    room_id: int | None
    status: Literal["online", "offline"]
    lux: float | None
    cct: int | None

    @classmethod
    def from_sensor(cls, sensor: Sensor) -> "SensorOut":
        return cls(
            id=sensor.id,
            name=sensor.name,
            room_id=sensor.room_id,
            status=sensor.status.value,
            lux=sensor.lux,
            cct=sensor.cct,
        )


class RoomSensorOut(BaseModel):
    id: int
    status: Literal["online", "offline"]
    lux: float | None
    cct: int | None


class NameIn(BaseModel):
    name: Name


# ---------- Комнаты ----------


class RoomOut(BaseModel):
    id: int
    name: str
    is_on: bool
    mode: Literal["manual", "auto"]
    brightness: float
    last_brightness: float
    target_lux: float
    color_mode: Literal["manual", "circadian"]
    color_temp_k: float
    sensor: RoomSensorOut | None
    lamps: list[RoomLampOut]
    power_w: float

    @classmethod
    def from_state(cls, state: RoomState) -> "RoomOut":
        room, sensor = state.room, state.sensor
        return cls(
            id=room.id,
            name=room.name,
            is_on=room.brightness > 0,
            mode=room.mode.value,
            brightness=room.brightness,
            last_brightness=room.last_brightness,
            target_lux=room.target_lux,
            color_mode=room.color_mode.value,
            color_temp_k=room.color_temp_k,
            sensor=None
            if sensor is None
            else RoomSensorOut(id=sensor.id, status=sensor.status.value, lux=sensor.lux, cct=sensor.cct),
            lamps=[
                RoomLampOut(
                    id=lamp.lamp.id,
                    name=lamp.lamp.name,
                    brightness=lamp.lamp.brightness,
                    color_temp_k=lamp.lamp.color_temp_k,
                    power_w=lamp.power_w,
                )
                for lamp in state.lamps
            ],
            power_w=state.power_w,
        )


class RoomCreate(BaseModel):
    name: Name
    target_lux: TargetLux | None = None


class RoomUpdate(BaseModel):
    name: Name | None = None
    target_lux: TargetLux | None = None


class ControlIn(BaseModel):
    mode: Literal["manual", "auto"] | None = None
    brightness: Brightness | None = None
    color_mode: Literal["manual", "circadian"] | None = None
    color_temp_k: ColorTempK | None = None


class PowerIn(BaseModel):
    on: bool
