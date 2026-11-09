import pytest

from lighting.hal import SensorError
from lighting.hardware.sensor import MULTIPLEXER_ADDRESS, Tcs34725Sensor


class FakeBus:
    """Двойник шины I2C: отдаёт заданные байты и запоминает обращения."""

    def __init__(self, payload: list[int] | None = None, error: Exception | None = None) -> None:
        self.payload = payload if payload is not None else [0] * 8
        self.error = error
        self.multiplexer_error: Exception | None = None
        self.byte_writes: list[tuple[int, int]] = []
        self.register_writes: list[tuple[int, int, int]] = []
        self.read_registers: list[int] = []

    def write_byte(self, address: int, value: int) -> None:
        if self.multiplexer_error is not None:
            raise self.multiplexer_error
        self.byte_writes.append((address, value))

    def write_byte_data(self, address: int, register: int, value: int) -> None:
        self.register_writes.append((address, register, value))

    def read_i2c_block_data(self, address: int, register: int, length: int) -> list[int]:
        self.read_registers.append(register)
        if self.error is not None:
            raise self.error
        return self.payload[:length]


def make_sensor(bus: FakeBus, channel: int | None = None) -> Tcs34725Sensor:
    return Tcs34725Sensor(bus=bus, channel=channel)


def test_reads_lux_and_colour_temperature() -> None:
    # C = 1000, R = 800, G = 1000, B = 600; младший байт идёт первым.
    bus = FakeBus([0xE8, 0x03, 0x20, 0x03, 0xE8, 0x03, 0x58, 0x02])

    reading = make_sensor(bus).read()

    assert reading.lux == pytest.approx(879.5, abs=0.1)
    assert reading.cct is not None
    assert 2900 <= reading.cct <= 3200


def test_configures_sensor_with_command_bit_on_first_read() -> None:
    bus = FakeBus()
    sensor = make_sensor(bus)
    assert bus.register_writes == []

    sensor.read()

    # Регистры ENABLE, ATIME и CONTROL со старшим битом, которого требует чип.
    registers = [register for _, register, _ in bus.register_writes]
    assert registers == [0x80, 0x81, 0x8F]


def test_reads_data_registers_with_auto_increment() -> None:
    bus = FakeBus()

    make_sensor(bus).read()

    assert bus.read_registers == [0xB4]


def test_selects_multiplexer_channel_before_each_read() -> None:
    bus = FakeBus()
    sensor = make_sensor(bus, channel=2)

    sensor.read()
    sensor.read()

    assert bus.byte_writes == [(MULTIPLEXER_ADDRESS, 0x04)] * 2


@pytest.mark.parametrize("channel", [-1, 8])
def test_rejects_channel_outside_multiplexer_range(channel: int) -> None:
    with pytest.raises(ValueError):
        make_sensor(FakeBus(), channel=channel)


def test_multiplexer_channel_seven_is_allowed() -> None:
    bus = FakeBus()

    make_sensor(bus, channel=7).read()

    assert bus.byte_writes == [(MULTIPLEXER_ADDRESS, 0x80)]


def test_darkness_gives_zero_lux_and_no_temperature() -> None:
    bus = FakeBus([0] * 8)

    reading = make_sensor(bus).read()

    assert reading.lux == 0.0
    assert reading.cct is None


def test_negative_lux_is_clamped_to_zero() -> None:
    # R = 2000, G = 100, B = 100: по формуле освещённость уходит в минус.
    bus = FakeBus([0xE8, 0x03, 0xD0, 0x07, 0x64, 0x00, 0x64, 0x00])

    reading = make_sensor(bus).read()

    assert reading.lux == 0.0
    assert reading.cct is None


def test_bus_error_becomes_sensor_error() -> None:
    bus = FakeBus(error=OSError("I2C NAK"))
    sensor = make_sensor(bus)

    with pytest.raises(SensorError):
        sensor.read()


def test_multiplexer_error_becomes_sensor_error() -> None:
    bus = FakeBus()
    bus.multiplexer_error = OSError("I2C NAK")
    sensor = make_sensor(bus, channel=1)

    with pytest.raises(SensorError):
        sensor.read()


def test_absent_sensor_does_not_break_start_and_is_configured_when_back() -> None:
    bus = FakeBus()
    bus.multiplexer_error = OSError("I2C NAK")
    sensor = make_sensor(bus, channel=1)
    with pytest.raises(SensorError):
        sensor.read()
    assert bus.register_writes == []

    bus.multiplexer_error = None
    sensor.read()

    assert [register for _, register, _ in bus.register_writes] == [0x80, 0x81, 0x8F]


def test_reconfigures_after_read_failure() -> None:
    bus = FakeBus()
    sensor = make_sensor(bus)
    sensor.read()
    bus.register_writes.clear()

    bus.error = OSError("I2C NAK")
    with pytest.raises(SensorError):
        sensor.read()
    bus.error = None
    sensor.read()

    assert len(bus.register_writes) == 3
