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
GP8403_MAX_PRESSURE = 130.534
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

def gp8403_set_range_0_10v(address: int = GP8403_DEFAULT_ADDRESS) -> None:
    """Put the GP8403 into 0–10 V output range."""
    try:
        _get_bus().write_i2c_block_data(address, 0x01, [0x11])
    except Exception as e:
        LOGGER.error("Failed to set 0–10 V range: %s", e)
        raise

def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def pressure_to_voltage(pressure_psi: float) -> float:
    """Map 0–100 psi → 0–10 V (values outside are clamped)."""
    p = _clamp(pressure_psi, GP8403_MIN_PRESSURE, GP8403_MAX_PRESSURE)
    proportion = (p - GP8403_MIN_PRESSURE) / (GP8403_MAX_PRESSURE - GP8403_MIN_PRESSURE)
    return GP8403_MIN_VOLTAGE + proportion * (GP8403_MAX_VOLTAGE - GP8403_MIN_VOLTAGE)

def voltage_to_code(voltage: float) -> int:
    """Convert 0–10 V → 12-bit code (0x000–0xFFF)."""
    v = _clamp(voltage, GP8403_MIN_VOLTAGE, GP8403_MAX_VOLTAGE)
    scale = GP8403_MAX_CODE / (GP8403_MAX_VOLTAGE - GP8403_MIN_VOLTAGE)
    code = int(round((v - GP8403_MIN_VOLTAGE) * scale))
    return _clamp(code, 0, GP8403_MAX_CODE)  # type: ignore[arg-type]


def _validate_channel(channel: int) -> int:
    if channel not in GP8403_CHANNEL_REGISTERS:
        raise ValueError(f"Invalid channel {channel}; must be one of {tuple(GP8403_CHANNEL_REGISTERS)}")
    return channel


def _write_channel_register(channel: int, code: int, address: int = GP8403_DEFAULT_ADDRESS) -> None:
    """Byte packing that matches your proven-working board order."""
    register = GP8403_CHANNEL_REGISTERS[channel]
    low_byte  = (code >> 4) & 0xFF          # bits 11..4
    high_byte = (code << 4) & 0xF0          # bits 3..0 -> bits 7..4
    try:
        _get_bus().write_i2c_block_data(address, register, [high_byte, low_byte])
    except Exception as e:
        LOGGER.error("I2C write failed (addr=0x%02X reg=0x%02X): %s", address, register, e)
        raise

def set_voltage(channel: int, voltage: float, address: int = GP8403_DEFAULT_ADDRESS) -> None:
    _validate_channel(channel)
    _write_channel_register(channel, voltage_to_code(voltage), address)

def set_pressure(channel: int, pressure_psi: float, address: int = GP8403_DEFAULT_ADDRESS) -> None:
    set_voltage(channel, pressure_to_voltage(pressure_psi), address)


def cleanup() -> None:
    global _bus
    if _bus is not None:
        try:
            _bus.close()
        finally:
            _bus = None

__all__ = [
    "pressure_to_voltage",
    "voltage_to_code",
    "set_voltage",
    "set_pressure",
    "gp8403_set_range_0_10v",
    "cleanup",
]