from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    name: str
    version: str
    runtime: Literal["virtual", "hardware"]
    time: datetime


class AuthCheckOut(BaseModel):
    ok: bool
