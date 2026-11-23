from fastapi import APIRouter, status

from lighting.api.deps import CONFLICT, NOT_FOUND, Service
from lighting.api.dto import ControlIn, PowerIn, RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/rooms", tags=["Комнаты"])


@router.get("", summary="Список комнат с состоянием")
def list_rooms(service: Service) -> list[RoomOut]:
    return [RoomOut.from_state(state) for state in service.list_rooms()]


@router.post("", summary="Создать комнату", status_code=status.HTTP_201_CREATED)
def create_room(body: RoomCreate, service: Service) -> RoomOut:
    return RoomOut.from_state(service.create_room(body.name, body.target_lux))


@router.get("/{room_id}", summary="Комната с лампами и датчиком", responses=NOT_FOUND)
def get_room(room_id: int, service: Service) -> RoomOut:
    return RoomOut.from_state(service.get_room(room_id))


@router.patch("/{room_id}", summary="Переименовать комнату или сменить целевую освещённость", responses=NOT_FOUND)
def update_room(room_id: int, body: RoomUpdate, service: Service) -> RoomOut:
    return RoomOut.from_state(service.update_room(room_id, body.name, body.target_lux))


@router.delete(
    "/{room_id}",
    summary="Удалить комнату (лампы и датчик отвязываются)",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
)
def delete_room(room_id: int, service: Service) -> None:
    service.delete_room(room_id)


@router.patch(
    "/{room_id}/control",
    summary="Яркость, оттенок и режимы комнаты",
    responses={**NOT_FOUND, **CONFLICT},
)
def control_room(room_id: int, body: ControlIn, service: Service) -> RoomOut:
    state = service.control(room_id, body.mode, body.brightness, body.color_mode, body.color_temp_k)
    return RoomOut.from_state(state)


@router.post("/{room_id}/power", summary="Включить (последняя уставка) или выключить", responses=NOT_FOUND)
def power_room(room_id: int, body: PowerIn, service: Service) -> RoomOut:
    return RoomOut.from_state(service.power(room_id, body.on))


@router.put("/{room_id}/lamps/{lamp_id}", summary="Привязать лампу", responses={**NOT_FOUND, **CONFLICT})
def bind_lamp(room_id: int, lamp_id: int, service: Service) -> RoomOut:
    return RoomOut.from_state(service.bind_lamp(room_id, lamp_id))


@router.delete("/{room_id}/lamps/{lamp_id}", summary="Отвязать лампу", responses=NOT_FOUND)
def unbind_lamp(room_id: int, lamp_id: int, service: Service) -> RoomOut:
    return RoomOut.from_state(service.unbind_lamp(room_id, lamp_id))


@router.put("/{room_id}/sensor/{sensor_id}", summary="Привязать датчик", responses={**NOT_FOUND, **CONFLICT})
def bind_sensor(room_id: int, sensor_id: int, service: Service) -> RoomOut:
    return RoomOut.from_state(service.bind_sensor(room_id, sensor_id))


@router.delete("/{room_id}/sensor/{sensor_id}", summary="Отвязать датчик", responses=NOT_FOUND)
def unbind_sensor(room_id: int, sensor_id: int, service: Service) -> RoomOut:
    return RoomOut.from_state(service.unbind_sensor(room_id, sensor_id))
