"""Точка входа: uvicorn lighting.runtime.main:app --reload"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lighting import __version__, api
from lighting.hal import Clock
from lighting.runtime.config import Settings
from lighting.service.system import SystemService

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger(__name__)


def create_clock(runtime: str) -> Clock:
    if runtime == "hardware":
        from lighting.hardware.clock import SystemClock

        return SystemClock()
    from lighting.sim.clock import VirtualClock

    return VirtualClock()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = create_clock(settings.runtime)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not settings.api_key:
            log.warning("API_KEY пустой: проверка X-API-Key отключена. Только для разработки!")
        log.info("Устройство запущено, режим %s", settings.runtime)
        yield

    app = FastAPI(title="LightningSystem", version=__version__, lifespan=lifespan)
    app.state.api_key = settings.api_key
    app.state.system_service = SystemService(
        clock=clock, name=settings.device_name, version=__version__, runtime=settings.runtime
    )
    app.include_router(api.router)
    return app


app = create_app()
