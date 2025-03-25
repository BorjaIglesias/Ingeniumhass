"""Config flow for Ingenium integration."""
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from ingeniumpy import IngeniumAPI

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA_FIRST = vol.Schema({
    vol.Optional("mode", default="remote"): vol.In(["remote", "local"])
})

DATA_SCHEMA_LOCAL = vol.Schema({
    CONF_HOST: str
})

DATA_SCHEMA_REMOTE = vol.Schema({
    CONF_USERNAME: str,
    CONF_PASSWORD: str
})


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = IngeniumAPI(hass)

    if CONF_USERNAME in data and CONF_PASSWORD in data:
        api.remote(data[CONF_USERNAME], data[CONF_PASSWORD])
    elif CONF_HOST in data:
        api.local(data[CONF_HOST])
    else:
        raise InvalidAuth

    result = await api.load(just_login=True)
    if not result:
        raise InvalidAuth

    return {"title": data[CONF_USERNAME] if CONF_USERNAME in data else data[CONF_HOST]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ingenium."""

    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            if "mode" in user_input:
                schema = DATA_SCHEMA_REMOTE if user_input["mode"] == "remote" else DATA_SCHEMA_LOCAL
                return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

            if CONF_HOST in user_input or (CONF_USERNAME in user_input and CONF_PASSWORD in user_input):
                try:
                    info = await validate_input(self.hass, user_input)
                    return self.async_create_entry(title=info["title"], data=user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception")
                    errors["base"] = "unknown"

        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA_FIRST, errors=errors)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
