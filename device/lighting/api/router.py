from fastapi import APIRouter, Depends

from lighting.api import system
from lighting.api.deps import require_api_key

# Ключ проверяется на уровне общего роутера: каждый новый роутер, подключённый
# к protected, получает защиту автоматически.
protected = APIRouter(dependencies=[Depends(require_api_key)])
protected.include_router(system.router)

router = APIRouter(prefix="/api/v1")
router.include_router(system.public_router)
router.include_router(protected)
