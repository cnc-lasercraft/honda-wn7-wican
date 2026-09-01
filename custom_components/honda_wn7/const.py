"""Constants for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "honda_wn7"

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SENSOR]

CONF_TOPIC_PREFIX = "topic_prefix"
CONF_RANGE_FACTOR = "range_factor"
CONF_SCALING = "scaling"

# How the WiCAN expressions were written. "scaled" means the AutoPID expression
# already converts to the physical unit (the configuration this repo
# documents); "raw" means the expression just reads the bytes and the
# conversion happens here.
SCALING_SCALED = "scaled"
SCALING_RAW = "raw"
DEFAULT_SCALING = SCALING_SCALED

DEFAULT_NAME = "Honda WN7"
DEFAULT_TOPIC_PREFIX = "wican/honda_wn7"

# km per SOC percent. 1.4 was measured on a 2026 EU WN7 (120 km ride consuming
# 85 %), which matches the ~140 km factory figure.
DEFAULT_RANGE_FACTOR = 1.4

# The state of charge the PV charge planning aims for. The WN7 does not expose
# its own charge limit — the full DID scan documented in PROTOCOL.md came back
# empty — so the rider sets the target and the number entity remembers it.
DEFAULT_CHARGE_LIMIT = 100.0
MIN_CHARGE_LIMIT = 50.0
MAX_CHARGE_LIMIT = 100.0

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
KEY_OBC_TEMP = "obc_temp"
KEY_PLUG = "plug"
KEY_CHARGE_STATE = "charge_state"

# The bike cuts CAN bus and 12 V within seconds of going to sleep, so every
# value goes stale. These are generous multiples of the polling periods
# recommended in the manual AutoPID configuration.
EXPIRE_FAST = 120
EXPIRE_MEDIUM = 300
EXPIRE_SLOW = 600

def convert_raw(key: str, value: float) -> float:
    """Convert a raw register value to its physical unit.

    Only used in "raw" mode. Everything not handled here reads the same in
    both modes: the percentages, the odometer, the plug and charge-state
    enums, and the pack current, which is a raw register either way.
    """
    if key == KEY_PACK_VOLTAGE:
        return value * 0.1
    if key in (KEY_CELL_TEMP, KEY_PORT_TEMP, KEY_OBC_TEMP):
        return value - 40
    if key in (KEY_CELL_MAX, KEY_CELL_MIN):
        return value / 5
    return value
