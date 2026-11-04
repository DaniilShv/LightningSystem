from gpiozero import DigitalOutputDevice, PWMOutputDevice

from lighting.hal import LightDriver

PWM_FREQUENCY_HZ = 1000


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class GpioLight(LightDriver):
    """CCT-лампа на Raspberry Pi: реле питания и два ШИМ-канала через MOSFET.

    Реле подаёт 12 В на ленту, транзисторы «тёплого» и «холодного» каналов
    задают её яркость и оттенок. Номера ножек — BCM, их передаёт runtime
    из описания подключённого железа.
    """

    def __init__(
        self,
        relay_pin: int,
        warm_pin: int,
        cool_pin: int,
        max_power_w: float,
    ) -> None:
        self._relay = DigitalOutputDevice(relay_pin, initial_value=False)
        self._warm = PWMOutputDevice(warm_pin, frequency=PWM_FREQUENCY_HZ, initial_value=0.0)
        self._cool = PWMOutputDevice(cool_pin, frequency=PWM_FREQUENCY_HZ, initial_value=0.0)
        self._max_power_w = max_power_w

    def set_output(self, relay: bool, warm: float, cool: float) -> None:
        warm = _clamp01(warm)
        cool = _clamp01(cool)
        if relay:
            # Сначала питание, потом каналы: иначе лента дёрнется на старом уровне.
            self._relay.on()
            self._warm.value = warm
            self._cool.value = cool
        else:
            # При выключении наоборот: гасим каналы и только затем снимаем питание.
            self._warm.value = 0.0
            self._cool.value = 0.0
            self._relay.off()

    @property
    def relay_closed(self) -> bool:
        """Подано ли питание на ленту."""
        return bool(self._relay.value)

    @property
    def duty(self) -> float:
        """Физическая доля света 0..1: сумма ШИМ каналов при замкнутом реле."""
        if not self.relay_closed:
            return 0.0
        return min(1.0, self._warm.value + self._cool.value)

    @property
    def power_w(self) -> float:
        """Мощность считается от duty, а не от воспринимаемой яркости."""
        return self._max_power_w * self.duty

    @property
    def closed(self) -> bool:
        """Освобождены ли ножки."""
        return self._relay.closed

    def close(self) -> None:
        """Погасить лампу и освободить ножки (вызывается при остановке устройства)."""
        if self.closed:
            return
        self._warm.value = 0.0
        self._cool.value = 0.0
        self._relay.off()
        self._warm.close()
        self._cool.close()
        self._relay.close()
