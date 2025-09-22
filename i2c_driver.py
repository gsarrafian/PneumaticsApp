"""Utilities for controlling the GP8403 4-channel 12-bit DAC over I2C."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

try:  # pragma: no cover - hardware dependency
    from smbus2 import SMBus as _HardwareSMBus
except ImportError:  # pragma: no cover - fallback for development environments
    _HardwareSMBus = None

LOGGER = logging.getLogger(__name__)

I2C_BUS_NUMBER = 1
GP8403_DEFAULT_ADDRESS = 0x5f
GP8403_CHANNEL_REGISTERS: Dict[int, int] = {
    1: 0x02,
    2: 0x04,
}

GP8403_MIN_VOLTAGE = 0.0
GP8403_MAX_VOLTAGE = 10.0
GP8403_MIN_PRESSURE = 0.0
GP8403_MAX_PRESSURE = 100.0
GP8403_MAX_CODE = 0x0FFF


@dataclass
class _MockSMBus:
    """Fallback SMBus implementation that only logs interactions."""

    bus: int
    closed: bool = False

    def write_i2c_block_data(self, addr: int, register: int, values: list[int]) -> None:
        LOGGER.debug(
            "Mock write to I2C addr=0x%02X register=0x%02X values=%s", addr, register, values
        )

    def close(self) -> None:
        self.closed = True
        LOGGER.debug("Mock SMBus on bus %s closed", self.bus)


_bus: Optional[object] = None


def _get_bus() -> object:
    """Lazily obtain an SMBus or mock replacement."""
    global _bus

    if _bus is None:
        if _HardwareSMBus is not None:
            LOGGER.debug("Opening hardware SMBus %s", I2C_BUS_NUMBER)
            _bus_instance = _HardwareSMBus(I2C_BUS_NUMBER)
        else:
            LOGGER.warning(
                "smbus2 is not available; using mock SMBus interface for development."
            )
            _bus_instance = _MockSMBus(I2C_BUS_NUMBER)
        _bus = _bus_instance

    return _bus


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def pressure_to_voltage(pressure_psi: float) -> float:
    """Translate a desired pressure in PSI to an output voltage.

    The GP8403 is typically paired with electro-pneumatic regulators that expect a
    0-10 V control signal representing 0-100 PSI. The mapping is linear.
    """

    clamped_pressure = _clamp(pressure_psi, GP8403_MIN_PRESSURE, GP8403_MAX_PRESSURE)
    voltage_span = GP8403_MAX_VOLTAGE - GP8403_MIN_VOLTAGE
    pressure_span = GP8403_MAX_PRESSURE - GP8403_MIN_PRESSURE

    if pressure_span == 0:
        return GP8403_MIN_VOLTAGE

    proportion = (clamped_pressure - GP8403_MIN_PRESSURE) / pressure_span
    return GP8403_MIN_VOLTAGE + proportion * voltage_span


def voltage_to_code(voltage: float) -> int:
    """Convert a voltage to the 12-bit GP8403 DAC code."""

    clamped_voltage = _clamp(voltage, GP8403_MIN_VOLTAGE, GP8403_MAX_VOLTAGE)
    scale = GP8403_MAX_CODE / (GP8403_MAX_VOLTAGE - GP8403_MIN_VOLTAGE)
    return int(round((clamped_voltage - GP8403_MIN_VOLTAGE) * scale))


def _validate_channel(channel: int) -> int:
    if channel not in GP8403_CHANNEL_REGISTERS:
        raise ValueError(f"Invalid channel {channel}; must be one of {tuple(GP8403_CHANNEL_REGISTERS)}")
    return channel


def _write_channel_register(channel: int, code: int) -> None:
    register = GP8403_CHANNEL_REGISTERS[channel]
    high_byte = (code >> 8) & 0xFF
    low_byte = code & 0xFF
    bus = _get_bus()
    bus.write_i2c_block_data(GP8403_DEFAULT_ADDRESS, register, [high_byte, low_byte])


def set_voltage(channel: int, voltage: float) -> None:
    """Set the output voltage for a DAC channel."""

    _validate_channel(channel)
    dac_code = voltage_to_code(voltage)
    _write_channel_register(channel, dac_code)


def set_pressure(channel: int, pressure_psi: float) -> None:
    """Set the output pressure (in PSI) for a DAC channel."""

    voltage = pressure_to_voltage(pressure_psi)
    set_voltage(channel, voltage)


def cleanup() -> None:
    """Close the I2C bus if it was opened."""

    global _bus

    if _bus is not None and hasattr(_bus, "close"):
        try:
            _bus.close()
        finally:
            _bus = None


__all__ = [
    "pressure_to_voltage",
    "voltage_to_code",
    "set_voltage",
    "set_pressure",
    "cleanup",
]