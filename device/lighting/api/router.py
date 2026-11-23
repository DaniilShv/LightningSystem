from fastapi import APIRouter, Depends

from lighting.api import registry, rooms, site, system
from lighting.api.deps import require_api_key
from lighting.api.dto import ErrorOut

# Ключ проверяется на уровне общего роутера: каждый новый роутер, подключённый
# к protected, получает защиту и описание ответа 401 в Swagger автоматически.
protected = APIRouter(
    dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorOut, "description": "Нет API-ключа или ключ неверный"}},
)
protected.include_router(system.router)
protected.include_router(site.router)
protected.include_router(rooms.router)
protected.include_router(registry.router)

router = APIRouter(prefix="/api/v1")
router.include_router(system.public_router)
router.include_router(protected)
