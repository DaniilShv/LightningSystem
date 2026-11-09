import time
from typing import Protocol

from lighting.hal import SensorDriver, SensorError, SensorReading

ADDRESS = 0x29
MULTIPLEXER_ADDRESS = 0x70

# В каждом обращении к регистру старший бит должен быть 1, иначе чип не считает
# байт адресом регистра. AUTO_INCREMENT нужен, чтобы читать несколько регистров подряд.
COMMAND_BIT = 0x80
AUTO_INCREMENT = 0x20

ENABLE_REGISTER = 0x00
ATIME_REGISTER = 0x01
CONTROL_REGISTER = 0x0F
CDATA_REGISTER = 0x14

ENABLE_POWER_ON = 0x03  # PON + AEN: питание и непрерывная интеграция
ATIME_50MS = 0xEB       # (256 - 235) * 2.4 мс ≈ 50 мс
GAIN_16X = 0x02
INTEGRATION_SECONDS = 0.05
MIN_LUX_FOR_CCT = 1.0

READING_REGISTERS = 8
MULTIPLEXER_CHANNELS = 8


class I2CBus(Protocol):
    """Минимум операций шины I2C, который нужен датчику.

    Такому протоколу соответствует smbus2.SMBus, а в тестах — простой двойник.
    """

    def write_byte(self, address: int, value: int) -> None: ...

    def write_byte_data(self, address: int, register: int, value: int) -> None: ...

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]: ...


class Tcs34725Sensor(SensorDriver):
    """Датчик света TCS34725 на шине I2C.

    Отдаёт две величины, как требует модель: освещённость и цветовую
    температуру. Если датчиков несколько, перед обращением выбирается
    канал мультиплексора TCA9548A.
    """

    def __init__(
        self,
        bus: I2CBus | None = None,
        address: int = ADDRESS,
        channel: int | None = None,
    ) -> None:
        if channel is not None and not 0 <= channel < MULTIPLEXER_CHANNELS:
            raise ValueError(f"Канал мультиплексора должен быть от 0 до {MULTIPLEXER_CHANNELS - 1}")
        if bus is None:
            # smbus2 работает только на Raspberry Pi: без I2C (например, на Windows) он не импортируется.
            from smbus2 import SMBus

            bus = SMBus(1)
        self._bus = bus
        self._address = address
        self._channel = channel
        self._configured = False

    def _configure(self) -> None:
        self._write(ENABLE_REGISTER, ENABLE_POWER_ON)
        self._write(ATIME_REGISTER, ATIME_50MS)
        self._write(CONTROL_REGISTER, GAIN_16X)
        # Датчику нужно время на первую интеграцию, иначе первые показания — нули.
        time.sleep(INTEGRATION_SECONDS * 2)
        self._configured = True

    def _select_channel(self) -> None:
        if self._channel is None:
            return
        self._bus.write_byte(MULTIPLEXER_ADDRESS, 1 << self._channel)

    def _write(self, register: int, value: int) -> None:
        self._bus.write_byte_data(self._address, COMMAND_BIT | register, value)

    def read(self) -> SensorReading:
        try:
            self._select_channel()
            # Настраиваем при первом чтении и после сбоя: датчик могли переподключить, и он
            # потерял настройки. Так отсутствие датчика при запуске не мешает устройству стартовать.
            if not self._configured:
                self._configure()
            data = self._bus.read_i2c_block_data(
                self._address, COMMAND_BIT | AUTO_INCREMENT | CDATA_REGISTER, READING_REGISTERS
            )
        except OSError as error:
            self._configured = False
            raise SensorError(f"Датчик {self._address:#04x} не ответил: {error}") from error

        clear = _word(data[0], data[1])
        if clear == 0:
            return SensorReading(lux=0.0, cct=None)

        red = _word(data[2], data[3])
        green = _word(data[4], data[5])
        blue = _word(data[6], data[7])
        lux = round(_lux(red, green, blue), 1)
        cct = _cct(red, green, blue) if lux >= MIN_LUX_FOR_CCT else None
        return SensorReading(lux=lux, cct=cct)


def _word(low: int, high: int) -> int:
    """Датчик отдаёт 16-битные значения младшим байтом вперёд."""
    return low | (high << 8)


def _lux(red: int, green: int, blue: int) -> float:
    """Освещённость по каналам RGB — упрощённая формула из даташита TCS3472."""
    return max(0.0, -0.32466 * red + 1.57837 * green - 0.73191 * blue)


def _cct(red: int, green: int, blue: int) -> int | None:
    """Цветовая температура по формуле Мак-Ками (даташит TCS3472)."""
    total = red + green + blue
    if total == 0:
        return None

    x = -0.14282 * red + 1.54924 * green - 0.95641 * blue
    y = -0.32466 * red + 1.57837 * green - 0.73191 * blue
    z = -0.68202 * red + 0.36281 * green + 0.42831 * blue
    sum_xyz = x + y + z
    if sum_xyz == 0:
        return None

    x_chroma = x / sum_xyz
    y_chroma = y / sum_xyz
    denominator = 0.1858 - y_chroma
    if denominator == 0:
        return None

    n = (x_chroma - 0.3320) / denominator
    kelvin = 449 * n**3 + 3525 * n**2 + 6823.3 * n + 5520.33
    if kelvin <= 0:
        return None
    return round(kelvin)
