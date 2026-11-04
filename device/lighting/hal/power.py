from abc import ABC, abstractmethod


class PowerMeter(ABC):
    """Источник данных о мощности.

    В virtual мощность рассчитывается из ШИМ (sim), в hardware её может дать
    настоящий датчик тока INA219.
    """

    @abstractmethod
    def total_power_w(self) -> float:
        """Суммарная мощность всех ламп прямо сейчас, Вт."""
