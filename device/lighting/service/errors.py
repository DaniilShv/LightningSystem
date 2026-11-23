from lighting.domain import RuleViolation


class NotFoundError(Exception):
    """Нет такой комнаты, лампы или датчика. В API превращается в ошибку 404."""


# api зависит только от service, поэтому ошибку правил модели отдаём ему отсюда.
__all__ = ["NotFoundError", "RuleViolation"]
