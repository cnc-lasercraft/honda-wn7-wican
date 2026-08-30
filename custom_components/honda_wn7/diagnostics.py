"""Diagnostics support for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bridge import WN7Bridge


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return the raw values last seen on each topic.

    Useful when reporting decoding findings from another WN7 — nothing here is
    personal, the values are the bike's own telemetry.
    """
    bridge: WN7Bridge = entry.runtime_data
    return {
        "topic_prefix": bridge.topic_prefix,
        "options": dict(entry.options),
        "readings": bridge.snapshot(),
    }
