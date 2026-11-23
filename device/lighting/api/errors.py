from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from lighting.service.errors import NotFoundError, RuleViolation

# Какие ошибки service в какие коды HTTP превращаются (docs/api.md, раздел «Ошибки»).
# Обработчики общие для всего приложения, поэтому в роутах нет try/except.
STATUS_BY_ERROR: dict[type[Exception], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    RuleViolation: status.HTTP_409_CONFLICT,
    ValueError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def register_error_handlers(app: FastAPI) -> None:
    for error_type, code in STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _handler(code))


def _handler(code: int):
    async def handle(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=code, content={"detail": str(error)})

    return handle
