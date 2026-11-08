from abc import ABC, abstractmethod


class PowerMeter(ABC):
    """Источник данных о мощности.

    В virtual мощность рассчитывается из ШИМ (sim), в hardware её может дать
    настоящий датчик тока INA219.
    """

    @abstractmethod
    def power_by_lamp_w(self) -> dict[int, float]:
        """Мощность каждой лампы прямо сейчас: {id лампы: Вт}.

        Энергия учитывается по лампам (docs/model.md), суммарная мощность — сумма значений.
        """
