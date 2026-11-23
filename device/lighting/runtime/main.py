"""Точка входа: uvicorn lighting.runtime.main:app --reload"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lighting import __version__, api
from lighting.api.errors import register_error_handlers
from lighting.hal import Clock, LightDriver, PowerMeter, SensorDriver
from lighting.runtime.config import Settings
from lighting.service.lighting import LightingService
from lighting.service.system import SystemService
from lighting.storage import Database, Registry, load_registry

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger(__name__)

OUTPUT_PERIOD_S = 0.03
DEFAULT_LUX_AT_FULL = 300.0
DEFAULT_WINDOW = 1.0
SENSOR_NOISE = 0.02  # шум показаний виртуального датчика ±2 % (docs/model.md)


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


def create_sensors(
    runtime: str, database: Database, registry: Registry, clock: Clock, lights: dict[int, LightDriver]
) -> dict[int, SensorDriver]:
    """Драйверы датчиков из базы. Опрашивает их цикл датчиков (telemetry), здесь они только создаются."""
    sensors = database.load_sensors()
    if runtime == "hardware":
        from lighting.hardware import Tcs34725Sensor

        drivers: dict[int, SensorDriver] = {}
        for sensor in sensors:
            try:
                drivers[sensor.id] = Tcs34725Sensor(
                    address=sensor.connection.address, channel=sensor.connection.mux_channel
                )
            except (ImportError, OSError) as error:
                # ImportError — не Raspberry Pi (нет smbus2), OSError — шина I2C выключена.
                # Устройство работает дальше, датчик просто остаётся оффлайн.
                log.error("Датчик «%s» не подключён: %s", sensor.name, error)
        return drivers

    from lighting.sim import VirtualSensor

    # Датчик видит лампы, которые физически на него светят (sees_lamps), а не привязанные к комнате в программе.
    return {
        sensor.id: VirtualSensor(
            clock=clock,
            window=registry.window.get(sensor.id, DEFAULT_WINDOW),
            lamps=[lights[lamp_id] for lamp_id in registry.sees_lamps.get(sensor.id, []) if lamp_id in lights],
            noise=SENSOR_NOISE,
        )
        for sensor in sensors
    }


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
        # Для цикла опроса датчиков и эндпоинтов /sim/* (раздел «Стыки между зонами» в AGENTS.md).
        app.state.sensor_drivers = create_sensors(settings.runtime, database, registry, clock, lights)
        app.state.clock = clock
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
