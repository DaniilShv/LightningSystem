from abc import ABC, abstractmethod


class LightDriver(ABC):
    """Драйвер одной лампы.

    Получает уже посчитанные каналы: domain переводит яркость и цветовую
    температуру в доли ШИМ и состояние реле, драйвер только применяет их.
    """

    @abstractmethod
    def set_output(self, relay: bool, warm: float, cool: float) -> None:
        """Применить состояние к железу.

        relay — замкнуто ли реле, то есть подано ли питание на ленту;
        warm, cool — доля времени «включено» для тёплого и холодного канала, 0.0..1.0.
        """
