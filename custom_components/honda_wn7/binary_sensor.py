"""Binary sensor platform for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .bridge import WN7Bridge
from .const import EXPIRE_FAST, EXPIRE_SLOW, KEY_CHARGE_STATE, KEY_PLUG, KEY_SOC
from .entity import WN7BaseEntity, WN7Entity
from .runtime import WN7Runtime
from .sensor import read_soc


@dataclass(frozen=True, kw_only=True)
class WN7BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Honda WN7 binary sensor."""

    source_keys: tuple[str, ...]
    value_fn: Callable[[WN7Bridge], bool | None]
    expire_after: int = EXPIRE_SLOW


def _cable_connected(bridge: WN7Bridge) -> bool | None:
    """Return whether a charge cable is plugged in.

    ``0xCB DB00`` byte 9: 1 = no cable, 3 = cable present. The value stays at 3
    during an active charge — there is no separate "charging" code in this byte.
    """
    value = bridge.value(KEY_PLUG)
    if value is None:
        return None
    return value >= 3


def _charging(bridge: WN7Bridge) -> bool | None:
    """Return whether the bike is actively charging.

    ``0xCB DB00`` byte 8: 1 = not charging (whether or not a cable is plugged
    in), 2 = charging.
    """
    value = bridge.value(KEY_CHARGE_STATE)
    if value is None:
        return None
    return value >= 2


BINARY_SENSORS: tuple[WN7BinarySensorEntityDescription, ...] = (
    WN7BinarySensorEntityDescription(
        key="charge_cable",
        translation_key="charge_cable",
        device_class=BinarySensorDeviceClass.PLUG,
        expire_after=EXPIRE_FAST,
        source_keys=(KEY_PLUG,),
        value_fn=_cable_connected,
    ),
    WN7BinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        source_keys=(KEY_CHARGE_STATE,),
        value_fn=_charging,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Honda WN7 binary sensors."""
    runtime: WN7Runtime = entry.runtime_data
    async_add_entities(
        [
            *(
                WN7BinarySensor(runtime.bridge, entry, description)
                for description in BINARY_SENSORS
            ),
            WN7PvChargeRequest(runtime, entry),
        ]
    )


class WN7BinarySensor(WN7Entity, BinarySensorEntity):
    """A flag decoded from the WN7's charge controller."""

    entity_description: WN7BinarySensorEntityDescription

    def __init__(
        self,
        bridge: WN7Bridge,
        entry: ConfigEntry,
        description: WN7BinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(
            bridge,
            entry,
            description.key,
            description.source_keys,
            description.expire_after,
        )
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.entity_description.value_fn(self._bridge)


ATTR_STATE_OF_CHARGE = "state_of_charge"
ATTR_CHARGING_LIMIT = "charging_limit"


class WN7PvChargeRequest(WN7BaseEntity, BinarySensorEntity, RestoreEntity):
    """Whether the bike still wants charge, for solar charge planning.

    Unlike every other entity here this one does not expire with the bike: a
    charge planner asks the question precisely when the WN7 has been plugged in
    and has gone back to sleep, so the last state of charge seen is carried
    across sleep phases and restarts. It is exposed alongside the target as
    attributes so a planner can work out the energy still needed:

        (charging_limit - state_of_charge) * capacity / 100
    """

    _attr_translation_key = "pv_charge_request"
    _attr_icon = "mdi:solar-power-variant"

    def __init__(self, runtime: WN7Runtime, entry: ConfigEntry) -> None:
        """Initialise the PV charge request."""
        super().__init__(entry, "pv_charge_request")
        self._bridge = runtime.bridge
        self._target = runtime.charge_target
        self._soc: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known charge and follow charge and target."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            try:
                self._soc = float(last.attributes[ATTR_STATE_OF_CHARGE])
            except (KeyError, TypeError, ValueError):
                self._soc = None
        self.async_on_remove(
            self._bridge.async_add_listener((KEY_SOC,), self._handle_update)
        )
        self.async_on_remove(self._target.async_add_listener(self._handle_update))
        # A charge may have arrived before this entity was added.
        self._read_soc()

    @callback
    def _handle_update(self) -> None:
        """Handle a new charge reading or a new target."""
        self._read_soc()
        self.async_write_ha_state()

    @callback
    def _read_soc(self) -> None:
        """Keep the last plausible state of charge; ignore going stale."""
        if (soc := read_soc(self._bridge)) is not None:
            self._soc = soc

    @property
    def is_on(self) -> bool | None:
        """Return whether the bike is below its target."""
        if self._soc is None:
            return None
        return self._soc < self._target.limit

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """Return the charge and target the answer was derived from."""
        return {
            ATTR_STATE_OF_CHARGE: self._soc,
            ATTR_CHARGING_LIMIT: self._target.limit,
        }
