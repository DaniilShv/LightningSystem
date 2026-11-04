import pytest
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin


@pytest.fixture(autouse=True)
def mock_gpio():
    """Подменяет все ножки виртуальными, чтобы драйверы тестировались без Pi."""
    previous = Device.pin_factory
    Device.pin_factory = MockFactory(pin_class=MockPWMPin)
    yield
    Device.pin_factory = previous
