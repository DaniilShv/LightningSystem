import secrets

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from lighting.service.system import SystemService

# auto_error=False: отсутствие заголовка обрабатываем сами, чтобы вернуть 401, а не 403.
# Заодно в Swagger появляется кнопка «Authorize».
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(request: Request, key: str | None = Security(api_key_header)) -> None:
    """Пропускает запрос, только если X-API-Key совпадает с ключом устройства.

    Пустой ключ устройства отключает проверку (только для разработки).
    """
    expected: str = request.app.state.api_key
    if not expected:
        return
    if key is None or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Нет API-ключа или ключ неверный")


def get_system_service(request: Request) -> SystemService:
    return request.app.state.system_service
