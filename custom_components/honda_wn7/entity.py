"""Base entity for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .bridge import WN7Bridge
from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER, MODEL


class WN7Entity(Entity):
    """Common behaviour for all Honda WN7 entities.

    Values only arrive while the bike is awake — ignition on or charging. A few
    seconds after key-off the CAN bus and the 12 V supply are cut and the WiCAN
    goes offline, so every entity expires on its own schedule and then reports
    unavailable instead of freezing at a stale value.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        bridge: WN7Bridge,
        entry: ConfigEntry,
        key: str,
        source_keys: tuple[str, ...],
        expire_after: int,
    ) -> None:
        """Initialise the entity."""
        self._bridge = bridge
        self._source_keys = source_keys
        self._expire_after = expire_after
        self._expiration_cancel: CALLBACK_TYPE | None = None
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or DEFAULT_NAME,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates for the keys this entity is built from."""
        self.async_on_remove(
            self._bridge.async_add_listener(self._source_keys, self._handle_update)
        )
        self.async_on_remove(self._cancel_expiration)
        self._schedule_expiration()

    @property
    def available(self) -> bool:
        """Return True while the underlying values are fresh."""
        age = self._bridge.age(self._source_keys)
        return age is not None and age <= self._expire_after

    @callback
    def _handle_update(self) -> None:
        """Handle a new value for one of our source keys."""
        self._schedule_expiration()
        self.async_write_ha_state()

    @callback
    def _schedule_expiration(self) -> None:
        """(Re)arm the timer that flips the entity to unavailable."""
        self._cancel_expiration()
        age = self._bridge.age(self._source_keys)
        if age is None:
            return
        delay = self._expire_after - age
        if delay <= 0:
            return
        self._expiration_cancel = async_call_later(self.hass, delay, self._expire)

    @callback
    def _cancel_expiration(self) -> None:
        """Cancel a pending expiration timer."""
        if self._expiration_cancel is not None:
            self._expiration_cancel()
            self._expiration_cancel = None

    @callback
    def _expire(self, _now: object) -> None:
        """Mark the entity unavailable once its value went stale."""
        self._expiration_cancel = None
        self.async_write_ha_state()
