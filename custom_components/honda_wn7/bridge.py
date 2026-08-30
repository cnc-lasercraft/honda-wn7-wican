"""MQTT bridge between the WiCAN AutoPID topics and Home Assistant."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCALING, SCALING_RAW, convert_raw

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class Reading:
    """A single value as last published by the WiCAN."""

    value: float
    received: float


class WN7Bridge:
    """Subscribes to the WiCAN topic tree and hands values to the entities.

    The WiCAN publishes one topic per configured PID, either as a bare number
    or as a single-key JSON object (``{"soc": 85.13}``) depending on firmware
    and configuration — both forms are accepted.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        topic_prefix: str,
        scaling: str = DEFAULT_SCALING,
    ) -> None:
        """Initialise the bridge."""
        self.hass = hass
        self.entry_id = entry_id
        self.topic_prefix = topic_prefix.rstrip("/")
        self.scaling = scaling
        self._readings: dict[str, Reading] = {}
        self._unsubscribe: Callable[[], None] | None = None

    @property
    def signal(self) -> str:
        """Dispatcher signal fired whenever a new value arrives."""
        return f"honda_wn7_update_{self.entry_id}"

    async def async_start(self) -> None:
        """Subscribe to the WiCAN topic tree."""
        self._unsubscribe = await mqtt.async_subscribe(
            self.hass, f"{self.topic_prefix}/#", self._async_message_received
        )

    @callback
    def async_stop(self) -> None:
        """Unsubscribe again."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _async_message_received(self, msg: mqtt.ReceiveMessage) -> None:
        """Store an incoming value and notify the entities interested in it."""
        key = msg.topic[len(self.topic_prefix) + 1 :]
        if not key or "/" in key:
            return

        value = _parse_payload(msg.payload, key)
        if value is None:
            _LOGGER.debug("Ignoring unparsable payload on %s: %r", msg.topic, msg.payload)
            return

        self._readings[key] = Reading(value=value, received=dt_util.utcnow().timestamp())
        async_dispatcher_send(self.hass, self.signal, key)

    @callback
    def async_add_listener(
        self, keys: tuple[str, ...], update: Callable[[], None]
    ) -> Callable[[], None]:
        """Call ``update`` whenever one of ``keys`` receives a new value."""

        @callback
        def _handle(key: str) -> None:
            if key in keys:
                update()

        return async_dispatcher_connect(self.hass, self.signal, _handle)

    @callback
    def get(self, key: str) -> float | None:
        """Return the last value for a key exactly as it was published."""
        reading = self._readings.get(key)
        return None if reading is None else reading.value

    @callback
    def value(self, key: str) -> float | None:
        """Return the last value for a key in its physical unit.

        In "raw" mode the WiCAN expression only reads the register, so the
        conversion to volts, °C or mV happens here instead.
        """
        raw = self.get(key)
        if raw is None or self.scaling != SCALING_RAW:
            return raw
        return convert_raw(key, raw)

    @callback
    def snapshot(self) -> dict[str, dict[str, float]]:
        """Return every value seen so far, with its age in seconds."""
        now = dt_util.utcnow().timestamp()
        return {
            key: {"value": reading.value, "age_seconds": round(now - reading.received, 1)}
            for key, reading in sorted(self._readings.items())
        }

    @callback
    def age(self, keys: tuple[str, ...]) -> float | None:
        """Return the age in seconds of the oldest of ``keys``.

        None means at least one of the keys has never been seen.
        """
        now = dt_util.utcnow().timestamp()
        ages: list[float] = []
        for key in keys:
            reading = self._readings.get(key)
            if reading is None:
                return None
            ages.append(now - reading.received)
        return max(ages) if ages else None


def _parse_payload(payload: str | bytes, key: str) -> float | None:
    """Parse a WiCAN payload into a float."""
    if isinstance(payload, bytes):
        try:
            payload = payload.decode()
        except UnicodeDecodeError:
            return None

    payload = payload.strip()
    if not payload:
        return None

    if payload.startswith("{"):
        try:
            data = json.loads(payload)
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        # Prefer the topic's own key, fall back to a single-entry object.
        if key in data:
            raw = data[key]
        elif len(data) == 1:
            raw = next(iter(data.values()))
        else:
            return None
    else:
        raw = payload

    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
