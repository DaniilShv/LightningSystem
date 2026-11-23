from fastapi import APIRouter

from lighting.api.deps import NOT_FOUND, Service
from lighting.api.dto import LampOut, NameIn, SensorOut

router = APIRouter()


@router.get("/lamps", summary="Реестр ламп (free=true — только свободные)", tags=["Лампы"])
def list_lamps(service: Service, free: bool = False) -> list[LampOut]:
    return [LampOut.from_state(state) for state in service.list_lamps(free)]


@router.patch("/lamps/{lamp_id}", summary="Переименовать лампу", tags=["Лампы"], responses=NOT_FOUND)
def rename_lamp(lamp_id: int, body: NameIn, service: Service) -> LampOut:
    return LampOut.from_state(service.rename_lamp(lamp_id, body.name))


@router.get("/sensors", summary="Реестр датчиков (free=true — только свободные)", tags=["Датчики"])
def list_sensors(service: Service, free: bool = False) -> list[SensorOut]:
    return [SensorOut.from_sensor(sensor) for sensor in service.list_sensors(free)]


@router.patch("/sensors/{sensor_id}", summary="Переименовать датчик", tags=["Датчики"], responses=NOT_FOUND)
def rename_sensor(sensor_id: int, body: NameIn, service: Service) -> SensorOut:
    return SensorOut.from_sensor(service.rename_sensor(sensor_id, body.name))

