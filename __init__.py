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
    _LOGGER.debug("Iniciando configuración de IngeniumAssistant")

    api = IngeniumAPI(hass)

    if CONF_USERNAME in entry.data and CONF_PASSWORD in entry.data:
        _LOGGER.debug("Autenticando en modo remoto con usuario: %s", entry.data[CONF_USERNAME])
        api.remote(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    elif CONF_HOST in entry.data:
        _LOGGER.debug("Conectando en modo local a host: %s", entry.data[CONF_HOST])
        api.local(entry.data[CONF_HOST])

    data_dir = hass.config.path(STORAGE_DIR, DOMAIN)

    def onchange(x: IngObject):
        _LOGGER.debug("Cambio detectado en: %s", x.address)
        async_dispatcher_send(hass, f"update_{DOMAIN}_{x.address}")

    # CORRECCIÓN: Ejecutar directamente await en api.load(), porque es una corutina async
    await api.load(debug=True, data_dir=data_dir, onchange=onchange)

    # Depuración: Verificar qué dispositivos detecta la API
    _LOGGER.debug("Termostatos detectados: %s", api.get_climates())
    _LOGGER.debug("Luces detectadas: %s", api.get_lights())
    _LOGGER.debug("Interruptores detectados: %s", api.get_switches())
    _LOGGER.debug("Persianas detectadas: %s", api.get_covers())
    _LOGGER.debug("Sensores detectados: %s", api.get_meterbuses())

    hass.data[DOMAIN][entry.entry_id] = api
    await hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        await api.close()

    return unload_ok