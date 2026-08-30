"""Constants for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "honda_wn7"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONF_TOPIC_PREFIX = "topic_prefix"
CONF_RANGE_FACTOR = "range_factor"

DEFAULT_NAME = "Honda WN7"
DEFAULT_TOPIC_PREFIX = "wican/honda_wn7"

# km per SOC percent. 1.4 was measured on a 2026 EU WN7 (120 km ride consuming
# 85 %), which matches the ~140 km factory figure.
DEFAULT_RANGE_FACTOR = 1.4

MANUFACTURER = "Honda"
MODEL = "WN7"

# Topic suffixes published by the WiCAN AutoPID configuration.
KEY_SOC = "soc"
KEY_SOC_DISPLAYED = "soc_disp"
KEY_ODOMETER = "odometer"
KEY_PACK_VOLTAGE = "pack_v"
KEY_PACK_CURRENT = "pack_i"
KEY_CELL_TEMP = "batt_temp"
KEY_SOH = "soh"
KEY_AMBIENT = "ambient"
KEY_CELL_MAX = "cell_max"
KEY_CELL_MIN = "cell_min"
KEY_PORT_TEMP = "port_temp"
KEY_PLUG = "plug"
KEY_CHARGE_STATE = "charge_state"

# The bike cuts CAN bus and 12 V within seconds of going to sleep, so every
# value goes stale. These are generous multiples of the polling periods
# recommended in the manual AutoPID configuration.
EXPIRE_FAST = 120
EXPIRE_MEDIUM = 300
EXPIRE_SLOW = 600
