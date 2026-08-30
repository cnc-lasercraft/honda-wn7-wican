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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import WN7Bridge
from .const import EXPIRE_FAST, EXPIRE_SLOW, KEY_CHARGE_STATE, KEY_PLUG
from .entity import WN7Entity


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
    value = bridge.get(KEY_PLUG)
    if value is None:
        return None
    return value >= 3


def _charging(bridge: WN7Bridge) -> bool | None:
    """Return whether the bike is actively charging.

    ``0xCB DB00`` byte 8: 1 = not charging (whether or not a cable is plugged
    in), 2 = charging.
    """
    value = bridge.get(KEY_CHARGE_STATE)
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
    bridge: WN7Bridge = entry.runtime_data
    async_add_entities(
        WN7BinarySensor(bridge, entry, description) for description in BINARY_SENSORS
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
