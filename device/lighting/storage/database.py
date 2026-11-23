import sqlite3
from pathlib import Path

from lighting.domain import (
    ColorMode,
    Lamp,
    LampPins,
    Mode,
    Room,
    Sensor,
    SensorConnection,
    Site,
)
from lighting.storage.registry import Registry

SCHEMA = """
CREATE TABLE IF NOT EXISTS site (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    tariff_rub_per_kwh REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_lux REAL NOT NULL,
    mode TEXT NOT NULL,
    brightness REAL NOT NULL,
    last_brightness REAL NOT NULL,
    color_mode TEXT NOT NULL,
    color_temp_k REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lamps (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    relay_pin INTEGER NOT NULL,
    warm_pin INTEGER NOT NULL,
    cool_pin INTEGER NOT NULL,
    max_power_w REAL NOT NULL,
    room_id INTEGER
);
CREATE TABLE IF NOT EXISTS sensors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    bus TEXT NOT NULL,
    address INTEGER NOT NULL,
    mux_channel INTEGER,
    room_id INTEGER
);
"""


class Database:
    """Хранение в SQLite: объект, комнаты, реестры ламп и датчиков, привязки.

    Сохраняются уставки и привязки (инвариант 11). Фактическая яркость ламп и показания
    датчиков не сохраняются: после перезапуска лампы плавно доходят до сохранённой уставки.
    Соединение одно на всё устройство; одновременный доступ из разных потоков
    разграничивает service своим замком.
    """

    def __init__(self, path: Path | str) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)

    def close(self) -> None:
        self._connection.close()

    def is_empty(self) -> bool:
        return self._connection.execute("SELECT COUNT(*) FROM site").fetchone()[0] == 0

    def seed(self, registry: Registry) -> None:
        """Залить реестры из device.toml. Только в пустую базу: дальше главная — база."""
        if not self.is_empty():
            raise RuntimeError("База уже заполнена")
        with self._connection:
            self._connection.execute(
                "INSERT INTO site (id, name, tariff_rub_per_kwh) VALUES (1, ?, ?)",
                (registry.site.name, registry.site.tariff_rub_per_kwh),
            )
            self._connection.executemany(
                "INSERT INTO lamps (id, name, relay_pin, warm_pin, cool_pin, max_power_w, room_id)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL)",
                [
                    (lamp.id, lamp.name, lamp.pins.relay, lamp.pins.warm, lamp.pins.cool, lamp.max_power_w)
                    for lamp in registry.lamps
                ],
            )
            self._connection.executemany(
                "INSERT INTO sensors (id, name, bus, address, mux_channel, room_id) VALUES (?, ?, ?, ?, ?, NULL)",
                [
                    (
                        sensor.id,
                        sensor.name,
                        sensor.connection.bus,
                        sensor.connection.address,
                        sensor.connection.mux_channel,
                    )
                    for sensor in registry.sensors
                ],
            )

    # ---------- Объект ----------

    def load_site(self) -> Site:
        row = self._connection.execute("SELECT name, tariff_rub_per_kwh FROM site WHERE id = 1").fetchone()
        return Site(name=row["name"], tariff_rub_per_kwh=row["tariff_rub_per_kwh"])

    def save_site(self, site: Site) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE site SET name = ?, tariff_rub_per_kwh = ? WHERE id = 1",
                (site.name, site.tariff_rub_per_kwh),
            )

    # ---------- Комнаты ----------

    def load_rooms(self) -> list[Room]:
        rows = self._connection.execute("SELECT * FROM rooms ORDER BY id").fetchall()
        return [_room_from_row(row) for row in rows]

    def insert_room(self, name: str, target_lux: float) -> Room:
        # Создаём сущность до вставки, чтобы проверки Room сработали раньше записи в базу.
        draft = Room(id=0, name=name, target_lux=target_lux)
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO rooms (name, target_lux, mode, brightness, last_brightness, color_mode, color_temp_k)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    draft.name,
                    draft.target_lux,
                    draft.mode.value,
                    draft.brightness,
                    draft.last_brightness,
                    draft.color_mode.value,
                    draft.color_temp_k,
                ),
            )
        return Room(id=cursor.lastrowid, name=name, target_lux=target_lux)

    def save_room(self, room: Room) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE rooms SET name = ?, target_lux = ?, mode = ?, brightness = ?, last_brightness = ?,"
                " color_mode = ?, color_temp_k = ? WHERE id = ?",
                (
                    room.name,
                    room.target_lux,
                    room.mode.value,
                    room.brightness,
                    room.last_brightness,
                    room.color_mode.value,
                    room.color_temp_k,
                    room.id,
                ),
            )

    def delete_room(self, room_id: int) -> None:
        """Удалить комнату и отвязать от неё лампы и датчик одной транзакцией (инвариант 3)."""
        with self._connection:
            self._connection.execute("UPDATE lamps SET room_id = NULL WHERE room_id = ?", (room_id,))
            self._connection.execute("UPDATE sensors SET room_id = NULL WHERE room_id = ?", (room_id,))
            self._connection.execute("DELETE FROM rooms WHERE id = ?", (room_id,))

    # ---------- Лампы и датчики ----------

    def load_lamps(self) -> list[Lamp]:
        rows = self._connection.execute("SELECT * FROM lamps ORDER BY id").fetchall()
        return [
            Lamp(
                id=row["id"],
                name=row["name"],
                pins=LampPins(relay=row["relay_pin"], warm=row["warm_pin"], cool=row["cool_pin"]),
                max_power_w=row["max_power_w"],
                room_id=row["room_id"],
            )
            for row in rows
        ]

    def save_lamp(self, lamp: Lamp) -> None:
        """Сохранить имя и привязку. Фактическая яркость не хранится."""
        with self._connection:
            self._connection.execute(
                "UPDATE lamps SET name = ?, room_id = ? WHERE id = ?", (lamp.name, lamp.room_id, lamp.id)
            )

    def load_sensors(self) -> list[Sensor]:
        rows = self._connection.execute("SELECT * FROM sensors ORDER BY id").fetchall()
        return [
            Sensor(
                id=row["id"],
                name=row["name"],
                connection=SensorConnection(
                    bus=row["bus"], address=row["address"], mux_channel=row["mux_channel"]
                ),
                room_id=row["room_id"],
            )
            for row in rows
        ]

    def save_sensor(self, sensor: Sensor) -> None:
        """Сохранить имя и привязку. Показания и статус не хранятся."""
        with self._connection:
            self._connection.execute(
                "UPDATE sensors SET name = ?, room_id = ? WHERE id = ?", (sensor.name, sensor.room_id, sensor.id)
            )


def _room_from_row(row: sqlite3.Row) -> Room:
    return Room(
        id=row["id"],
        name=row["name"],
        target_lux=row["target_lux"],
        mode=Mode(row["mode"]),
        brightness=row["brightness"],
        last_brightness=row["last_brightness"],
        color_mode=ColorMode(row["color_mode"]),
        color_temp_k=row["color_temp_k"],
    )
