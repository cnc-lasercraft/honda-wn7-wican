"""Shared runtime objects for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from .bridge import WN7Bridge


class WN7ChargeTarget:
    """The state of charge the rider wants the bike charged to.

    The WN7 keeps its own charge limit to itself — the full DID scan documented
    in PROTOCOL.md never found it — so anything planning a charge has to be
    told what to aim for. The number entity writes the target here, the PV
    charge request reads it, and both are notified when it changes.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str, limit: float) -> None:
        """Initialise the target with the value to use until one is restored."""
        self.hass = hass
        self.entry_id = entry_id
        self._limit = limit

    @property
    def signal(self) -> str:
        """Dispatcher signal fired whenever the target changes."""
        return f"honda_wn7_charge_target_{self.entry_id}"

    @property
    def limit(self) -> float:
        """Return the state of charge to stop at, in percent."""
        return self._limit

    @callback
    def async_set_limit(self, limit: float) -> None:
        """Set a new target and tell everyone reading it."""
        self._limit = limit
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Call ``update`` whenever the target changes."""
        return async_dispatcher_connect(self.hass, self.signal, update)


@dataclass(slots=True)
class WN7Runtime:
    """Everything the platforms share, hung off the config entry."""

    bridge: WN7Bridge
    charge_target: WN7ChargeTarget
