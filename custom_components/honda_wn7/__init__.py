"""The Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .bridge import WN7Bridge
from .const import CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Honda WN7 from a config entry."""
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT integration is not available")

    bridge = WN7Bridge(
        hass,
        entry.entry_id,
        entry.data.get(CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX),
    )
    await bridge.async_start()
    entry.runtime_data = bridge

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        bridge: WN7Bridge = entry.runtime_data
        bridge.async_stop()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when its options changed."""
    await hass.config_entries.async_reload(entry.entry_id)
