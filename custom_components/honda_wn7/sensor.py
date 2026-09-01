"""Sensor platform for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import WN7Bridge
from .const import (
    CONF_RANGE_FACTOR,
    DEFAULT_RANGE_FACTOR,
    EXPIRE_FAST,
    EXPIRE_MEDIUM,
    EXPIRE_SLOW,
    KEY_AMBIENT,
    KEY_CELL_MAX,
    KEY_CELL_MIN,
    KEY_CELL_TEMP,
    KEY_OBC_TEMP,
    KEY_ODOMETER,
    KEY_PACK_CURRENT,
    KEY_PACK_VOLTAGE,
    KEY_PORT_TEMP,
    KEY_SOC,
    KEY_SOC_DISPLAYED,
    KEY_SOH,
)
from .entity import WN7Entity


@dataclass(frozen=True, kw_only=True)
class WN7SensorEntityDescription(SensorEntityDescription):
    """Describes a Honda WN7 sensor."""

    source_keys: tuple[str, ...]
    value_fn: Callable[[WN7Bridge], float | None]
    expire_after: int = EXPIRE_SLOW


def read_soc(bridge: WN7Bridge) -> float | None:
    """Return the BMS SOC, rejecting the garbage a mid-poll reboot can emit.

    A WiCAN restart in the middle of a request yields 0 or a nonsensical value
    above the physical maximum; anything outside 0 < x <= 100.5 is dropped and
    the rest is capped at 100.
    """
    value = bridge.value(KEY_SOC)
    if value is None or not 0 < value <= 100.5:
        return None
    return round(min(value, 100.0), 1)


def _odometer(bridge: WN7Bridge) -> float | None:
    """Return the odometer, rejecting the 6553.5 km plateau of a truncated read."""
    value = bridge.value(KEY_ODOMETER)
    if value is None or not 0 < value < 6553:
        return None
    return round(value, 1)


def _pack_current(bridge: WN7Bridge) -> float | None:
    """Return the pack current in amps.

    The WiCAN publishes the raw unsigned 16-bit register; values above 32767
    are negative. Positive means the pack is being discharged (riding),
    negative means current flows into the pack (charging or regen).
    """
    raw = bridge.value(KEY_PACK_CURRENT)
    if raw is None:
        return None
    if raw > 32767:
        raw -= 65536
    return round(raw / 10, 1)


def _battery_power(bridge: WN7Bridge) -> float | None:
    """Return pack power in watts, positive while discharging."""
    voltage = bridge.value(KEY_PACK_VOLTAGE)
    current = _pack_current(bridge)
    if voltage is None or current is None:
        return None
    return round(voltage * current, 0)


def _cell_voltage(key: str) -> Callable[[WN7Bridge], float | None]:
    """Return a reader for a cell voltage published either in mV or in V."""

    def _read(bridge: WN7Bridge) -> float | None:
        value = bridge.value(key)
        if value is None or value <= 0:
            return None
        # The manual AutoPID config publishes millivolts, the upstream vehicle
        # profile publishes volts — normalise both to millivolts.
        if value < 100:
            value *= 1000
        return round(value, 1)

    return _read


def _plain(key: str) -> Callable[[WN7Bridge], float | None]:
    """Return a reader that passes the published value through unchanged."""

    def _read(bridge: WN7Bridge) -> float | None:
        return bridge.value(key)

    return _read


SENSORS: tuple[WN7SensorEntityDescription, ...] = (
    WN7SensorEntityDescription(
        key="soc",
        translation_key="soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        source_keys=(KEY_SOC,),
        value_fn=read_soc,
    ),
    WN7SensorEntityDescription(
        key="soc_displayed",
        translation_key="soc_displayed",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        source_keys=(KEY_SOC_DISPLAYED,),
        value_fn=_plain(KEY_SOC_DISPLAYED),
    ),
    WN7SensorEntityDescription(
        key="odometer",
        translation_key="odometer",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=1,
        source_keys=(KEY_ODOMETER,),
        value_fn=_odometer,
    ),
    WN7SensorEntityDescription(
        key="pack_voltage",
        translation_key="pack_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        expire_after=EXPIRE_FAST,
        source_keys=(KEY_PACK_VOLTAGE,),
        value_fn=_plain(KEY_PACK_VOLTAGE),
    ),
    WN7SensorEntityDescription(
        key="pack_current",
        translation_key="pack_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        expire_after=EXPIRE_FAST,
        source_keys=(KEY_PACK_CURRENT,),
        value_fn=_pack_current,
    ),
    WN7SensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        expire_after=EXPIRE_FAST,
        source_keys=(KEY_PACK_VOLTAGE, KEY_PACK_CURRENT),
        value_fn=_battery_power,
    ),
    WN7SensorEntityDescription(
        key="cell_temperature",
        translation_key="cell_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_CELL_TEMP,),
        value_fn=_plain(KEY_CELL_TEMP),
    ),
    WN7SensorEntityDescription(
        key="battery_health",
        translation_key="battery_health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        source_keys=(KEY_SOH,),
        value_fn=_plain(KEY_SOH),
    ),
    WN7SensorEntityDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_AMBIENT,),
        value_fn=_plain(KEY_AMBIENT),
    ),
    WN7SensorEntityDescription(
        key="charge_port_temperature",
        translation_key="charge_port_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_PORT_TEMP,),
        value_fn=_plain(KEY_PORT_TEMP),
    ),
    WN7SensorEntityDescription(
        key="obc_temperature",
        translation_key="obc_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=0,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_OBC_TEMP,),
        value_fn=_plain(KEY_OBC_TEMP),
    ),
    WN7SensorEntityDescription(
        key="cell_voltage_max",
        translation_key="cell_voltage_max",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_CELL_MAX,),
        value_fn=_cell_voltage(KEY_CELL_MAX),
    ),
    WN7SensorEntityDescription(
        key="cell_voltage_min",
        translation_key="cell_voltage_min",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        expire_after=EXPIRE_MEDIUM,
        source_keys=(KEY_CELL_MIN,),
        value_fn=_cell_voltage(KEY_CELL_MIN),
    ),
)


def _range_description(factor: float) -> WN7SensorEntityDescription:
    """Build the range estimate, which depends on the configured km/% factor."""

    def _range(bridge: WN7Bridge) -> float | None:
        soc = read_soc(bridge)
        if soc is None:
            return None
        return round(soc * factor)

    return WN7SensorEntityDescription(
        key="range",
        translation_key="range",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        source_keys=(KEY_SOC,),
        value_fn=_range,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Honda WN7 sensors."""
    bridge: WN7Bridge = entry.runtime_data.bridge
    factor = entry.options.get(
        CONF_RANGE_FACTOR, entry.data.get(CONF_RANGE_FACTOR, DEFAULT_RANGE_FACTOR)
    )
    descriptions = (*SENSORS, _range_description(float(factor)))
    async_add_entities(
        WN7Sensor(bridge, entry, description) for description in descriptions
    )


class WN7Sensor(WN7Entity, SensorEntity):
    """A single value read off the WN7's CAN bus."""

    entity_description: WN7SensorEntityDescription

    def __init__(
        self,
        bridge: WN7Bridge,
        entry: ConfigEntry,
        description: WN7SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(
            bridge,
            entry,
            description.key,
            description.source_keys,
            description.expire_after,
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self._bridge)

    @property
    def available(self) -> bool:
        """Return True only while a plausible, fresh value is present."""
        return super().available and self.native_value is not None
