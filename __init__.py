"""The Ingenium integration."""
import voluptuous as vol
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngObject
from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("mode", default="remote"): vol.In(["remote", "local"]),
                vol.Optional(CONF_HOST): cv.string,
                vol.Optional(CONF_USERNAME): cv.string,
                vol.Optional(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType):
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = IngeniumAPI(hass)

    if CONF_USERNAME in entry.data and CONF_PASSWORD in entry.data:
        api.remote(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    elif CONF_HOST in entry.data:
        api.local(entry.data[CONF_HOST])

    data_dir = hass.config.path(STORAGE_DIR, DOMAIN)

    def onchange(x: IngObject):
        async_dispatcher_send(hass, f"update_{DOMAIN}_{x.address}")

    # Ejecutar en hilo separado para evitar bloqueo
    await hass.async_add_executor_job(api.load, False, data_dir, onchange)

    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        await api.close()

    return unload_ok