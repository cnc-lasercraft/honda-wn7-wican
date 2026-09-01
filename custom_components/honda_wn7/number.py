"""Number platform for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import MAX_CHARGE_LIMIT, MIN_CHARGE_LIMIT
from .entity import WN7BaseEntity
from .runtime import WN7Runtime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Honda WN7 numbers."""
    runtime: WN7Runtime = entry.runtime_data
    async_add_entities([WN7ChargeLimit(runtime, entry)])


class WN7ChargeLimit(WN7BaseEntity, RestoreNumber):
    """The state of charge the rider wants the bike charged to.

    This is a target, not a command: the WN7 neither reports nor accepts a
    charge limit over the diagnostic bus, so nothing here reaches the bike. It
    exists so charge planning — see the PV charge request binary sensor — knows
    when the battery counts as full.
    """

    _attr_translation_key = "charge_limit"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = NumberDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = MIN_CHARGE_LIMIT
    _attr_native_max_value = MAX_CHARGE_LIMIT
    _attr_native_step = 5
    _attr_mode = NumberMode.SLIDER

    def __init__(self, runtime: WN7Runtime, entry: ConfigEntry) -> None:
        """Initialise the charge limit."""
        super().__init__(entry, "charge_limit")
        self._target = runtime.charge_target

    async def async_added_to_hass(self) -> None:
        """Restore the target the rider last set."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._target.async_set_limit(
                min(max(last.native_value, MIN_CHARGE_LIMIT), MAX_CHARGE_LIMIT)
            )

    @property
    def native_value(self) -> float:
        """Return the current target."""
        return self._target.limit

    async def async_set_native_value(self, value: float) -> None:
        """Set a new target."""
        self._target.async_set_limit(value)
        self.async_write_ha_state()
