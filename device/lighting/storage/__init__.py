"""Хранение в SQLite через стандартный sqlite3: реестры, комнаты, режимы, уставки, привязки, история.

Переводит сущности domain в таблицы и обратно. Зависит только от domain.
Реестр подключённого железа читается из device/device.toml стандартным tomllib.
"""

from lighting.storage.database import Database
from lighting.storage.registry import Registry, load_registry

__all__ = ["Database", "Registry", "load_registry"]
