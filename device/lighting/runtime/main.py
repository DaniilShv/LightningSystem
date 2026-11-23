"""Точка входа: uvicorn lighting.runtime.main:app --reload"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lighting import __version__, api
from lighting.api.errors import register_error_handlers
from lighting.hal import Clock, LightDriver, PowerMeter
from lighting.runtime.config import Settings
from lighting.service.lighting import LightingService
from lighting.service.system import SystemService
from lighting.storage import Database, Registry, load_registry

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger(__name__)

OUTPUT_PERIOD_S = 0.03
DEFAULT_LUX_AT_FULL = 300.0


def create_clock(runtime: str) -> Clock:
    if runtime == "hardware":
        from lighting.hardware.clock import SystemClock

        return SystemClock()
    from lighting.sim.clock import VirtualClock

    return VirtualClock()


def create_lights(runtime: str, database: Database, registry: Registry) -> tuple[dict[int, LightDriver], PowerMeter]:
    """Драйверы ламп из базы. Импорт внутри функции: gpiozero нужен только на настоящей Pi."""
    lamps = database.load_lamps()
    if runtime == "hardware":
        from lighting.hardware import EstimatedPowerMeter, GpioLight

        gpio = {
            lamp.id: GpioLight(lamp.pins.relay, lamp.pins.warm, lamp.pins.cool, lamp.max_power_w) for lamp in lamps
        }
        return dict(gpio), EstimatedPowerMeter(gpio)

    from lighting.sim import VirtualLight, VirtualPowerMeter

    virtual = {
        lamp.id: VirtualLight(lamp.max_power_w, registry.lux_at_full.get(lamp.id, DEFAULT_LUX_AT_FULL))
        for lamp in lamps
    }
    return dict(virtual), VirtualPowerMeter(virtual)


async def output_loop(service: LightingService, clock: Clock) -> None:
    """Цикл вывода: примерно 30 раз в секунду лампы плавно догоняют уставки комнат."""
    last = clock.now()
    while True:
        await asyncio.sleep(OUTPUT_PERIOD_S)
        now = clock.now()
        try:
            service.tick((now - last).total_seconds())
        except Exception:
            # Цикл не должен падать: ошибка в лог, работа продолжается.
            log.exception("Ошибка в цикле вывода на лампы")
        last = now


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = create_clock(settings.runtime)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not settings.api_key:
            log.warning("API_KEY пустой: проверка X-API-Key отключена. Только для разработки!")

        # Реестр читаем при каждом запуске: он проверяет device.toml и даёт параметры виртуального железа.
        registry = load_registry(settings.registry_path)
        database = Database(settings.db_path)
        if database.is_empty():
            database.seed(registry)
            log.info("База пустая: реестры ламп и датчиков заполнены из %s", settings.registry_path.name)

        lights, power_meter = create_lights(settings.runtime, database, registry)
        service = LightingService(database, lights, power_meter, settings.fade_ms)
        app.state.lighting_service = service
        loop = asyncio.create_task(output_loop(service, clock))
        log.info("Устройство запущено, режим %s", settings.runtime)
        try:
            yield
        finally:
            loop.cancel()
            try:
                await loop
            except asyncio.CancelledError:
                pass
            service.close()
            database.close()
            log.info("Устройство остановлено: лампы погашены, ножки освобождены")

    app = FastAPI(title="LightningSystem", version=__version__, lifespan=lifespan)
    app.state.api_key = settings.api_key
    app.state.system_service = SystemService(
        clock=clock, name=settings.device_name, version=__version__, runtime=settings.runtime
    )
    register_error_handlers(app)
    app.include_router(api.router)
    return app


app = create_app()
