"""Config flow for the Honda WN7 (WiCAN) integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_RANGE_FACTOR,
    CONF_SCALING,
    CONF_TOPIC_PREFIX,
    DEFAULT_NAME,
    DEFAULT_RANGE_FACTOR,
    DEFAULT_SCALING,
    DEFAULT_TOPIC_PREFIX,
    DOMAIN,
    SCALING_RAW,
    SCALING_SCALED,
)

RANGE_FACTOR_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0.1, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX
    )
)

SCALING_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[SCALING_SCALED, SCALING_RAW],
        translation_key="scaling",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)


class HondaWN7ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the MQTT topic prefix the WiCAN publishes to."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            prefix = user_input[CONF_TOPIC_PREFIX].strip().strip("/")
            try:
                mqtt.valid_subscribe_topic(f"{prefix}/#")
            except vol.Invalid:
                errors[CONF_TOPIC_PREFIX] = "invalid_topic"
            else:
                await self.async_set_unique_id(prefix)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_TOPIC_PREFIX: prefix},
                    options={
                        CONF_RANGE_FACTOR: user_input.get(
                            CONF_RANGE_FACTOR, DEFAULT_RANGE_FACTOR
                        ),
                        CONF_SCALING: user_input.get(CONF_SCALING, DEFAULT_SCALING),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TOPIC_PREFIX,
                        default=(user_input or {}).get(
                            CONF_TOPIC_PREFIX, DEFAULT_TOPIC_PREFIX
                        ),
                    ): str,
                    vol.Required(
                        CONF_RANGE_FACTOR, default=DEFAULT_RANGE_FACTOR
                    ): RANGE_FACTOR_SELECTOR,
                    vol.Required(
                        CONF_SCALING, default=DEFAULT_SCALING
                    ): SCALING_SELECTOR,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HondaWN7OptionsFlow()


class HondaWN7OptionsFlow(OptionsFlow):
    """Let the user retune the range estimate."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RANGE_FACTOR,
                        default=options.get(CONF_RANGE_FACTOR, DEFAULT_RANGE_FACTOR),
                    ): RANGE_FACTOR_SELECTOR,
                    vol.Required(
                        CONF_SCALING,
                        default=options.get(CONF_SCALING, DEFAULT_SCALING),
                    ): SCALING_SELECTOR,
                }
            ),
        )
