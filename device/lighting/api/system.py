from typing import Annotated

from fastapi import APIRouter, Depends

from lighting.api.deps import get_system_service
from lighting.api.dto import AuthCheckOut, HealthOut
from lighting.service.system import SystemService

public_router = APIRouter(tags=["Система"])
router = APIRouter(tags=["Система"])


@public_router.get("/health", summary="Устройство на связи (без ключа)")
def health(service: Annotated[SystemService, Depends(get_system_service)]) -> HealthOut:
    info = service.info()
    return HealthOut(name=info.name, version=info.version, runtime=info.runtime, time=info.time)


@router.get("/auth/check", summary="Проверить API-ключ")
def auth_check() -> AuthCheckOut:
    return AuthCheckOut(ok=True)
