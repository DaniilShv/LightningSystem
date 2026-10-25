"""HTTP-транспорт: роуты, DTO, ошибки, проверка API-ключа. Без логики, вызывает только service.

runtime кладёт в app.state всё, что нужно роутам (см. api/deps.py).
"""

from lighting.api.router import router

__all__ = ["router"]
