from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEVICE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Настройки устройства. Берутся из переменных окружения и device/.env."""

    model_config = SettingsConfigDict(env_file=DEVICE_DIR / ".env", env_file_encoding="utf-8")

    runtime: Literal["virtual", "hardware"] = "virtual"
    # Пустой ключ отключает проверку X-API-Key (только для разработки).
    api_key: str = ""
    device_name: str = "LightningSystem"
