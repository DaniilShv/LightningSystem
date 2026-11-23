import tomllib
from dataclasses import dataclass
from pathlib import Path

from lighting.domain import Lamp, LampPins, Sensor, SensorConnection, Site

FIRST_FREE_PIN = 4
LAST_FREE_PIN = 27
MULTIPLEXER_CHANNELS = 8


@dataclass(frozen=True)
class Registry:
    """Что физически подключено: содержимое device/device.toml.

    lux_at_full, window и sees_lamps нужны только виртуальному железу (sim), поэтому в сущностях domain их нет.
    sees_lamps — какие лампы физически светят на датчик: {id датчика: [id ламп]}.
    """

    site: Site
    lamps: list[Lamp]
    sensors: list[Sensor]
    lux_at_full: dict[int, float]
    window: dict[int, float]
    sees_lamps: dict[int, list[int]]


def load_registry(path: Path) -> Registry:
    with open(path, "rb") as file:
        data = tomllib.load(file)

    site = Site(name=data["site"]["name"], tariff_rub_per_kwh=data["site"]["tariff_rub_per_kwh"])
    lamps = [
        Lamp(
            id=item["id"],
            name=item["name"],
            pins=LampPins(relay=item["pins"]["relay"], warm=item["pins"]["warm"], cool=item["pins"]["cool"]),
            max_power_w=item["max_power_w"],
        )
        for item in data.get("lamps", [])
    ]
    sensors = [
        Sensor(
            id=item["id"],
            name=item["name"],
            connection=SensorConnection(
                bus=item["bus"], address=item["address"], mux_channel=item.get("mux_channel")
            ),
        )
        for item in data.get("sensors", [])
    ]
    sees_lamps = {item["id"]: list(item.get("sees_lamps", [])) for item in data.get("sensors", [])}
    _check_lamps(lamps)
    _check_sensors(sensors, sees_lamps, {lamp.id for lamp in lamps})
    return Registry(
        site=site,
        lamps=lamps,
        sensors=sensors,
        lux_at_full={item["id"]: item["lux_at_full"] for item in data.get("lamps", [])},
        window={item["id"]: item["window"] for item in data.get("sensors", [])},
        sees_lamps=sees_lamps,
    )


def _check_lamps(lamps: list[Lamp]) -> None:
    _check_unique_ids("ламп", [lamp.id for lamp in lamps])
    used: dict[int, str] = {}
    for lamp in lamps:
        for pin in (lamp.pins.relay, lamp.pins.warm, lamp.pins.cool):
            if not FIRST_FREE_PIN <= pin <= LAST_FREE_PIN:
                raise ValueError(f"Лампа «{lamp.name}»: ножка GPIO{pin} вне BCM {FIRST_FREE_PIN}–{LAST_FREE_PIN}")
            if pin in used:
                raise ValueError(f"Ножка GPIO{pin} занята дважды: «{used[pin]}» и «{lamp.name}»")
            used[pin] = lamp.name


def _check_sensors(sensors: list[Sensor], sees_lamps: dict[int, list[int]], lamp_ids: set[int]) -> None:
    _check_unique_ids("датчиков", [sensor.id for sensor in sensors])
    for sensor in sensors:
        channel = sensor.connection.mux_channel
        if channel is not None and not 0 <= channel < MULTIPLEXER_CHANNELS:
            raise ValueError(f"Датчик «{sensor.name}»: mux_channel должен быть от 0 до {MULTIPLEXER_CHANNELS - 1}")
        unknown = set(sees_lamps[sensor.id]) - lamp_ids
        if unknown:
            raise ValueError(f"Датчик «{sensor.name}»: в sees_lamps нет таких ламп {sorted(unknown)}")
    if len(sensors) < 2:
        return
    # У TCS34725 адрес фиксированный, поэтому несколько датчиков различаются только каналом мультиплексора.
    channels = [sensor.connection.mux_channel for sensor in sensors]
    if None in channels:
        raise ValueError("Датчиков несколько: у каждого должен быть свой mux_channel")
    if len(set(channels)) != len(channels):
        raise ValueError("Каналы мультиплексора у датчиков повторяются")


def _check_unique_ids(what: str, ids: list[int]) -> None:
    if len(set(ids)) != len(ids):
        raise ValueError(f"id {what} в реестре повторяются")
