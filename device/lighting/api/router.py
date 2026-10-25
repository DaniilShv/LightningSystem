from fastapi import APIRouter, Depends

from lighting.api import system
from lighting.api.deps import require_api_key
from lighting.api.dto import ErrorOut

# Ключ проверяется на уровне общего роутера: каждый новый роутер, подключённый
# к protected, получает защиту и описание ответа 401 в Swagger автоматически.
protected = APIRouter(
    dependencies=[Depends(require_api_key)],
    responses={401: {"model": ErrorOut, "description": "Нет API-ключа или ключ неверный"}},
)
protected.include_router(system.router)

router = APIRouter(prefix="/api/v1")
router.include_router(system.public_router)
router.include_router(protected)
