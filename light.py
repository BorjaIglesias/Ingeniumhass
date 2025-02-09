import logging

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngBusingRegulator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IngLight(o) for o in api.get_lights()])

class IngLight(LightEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, obj: IngBusingRegulator):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
        self._attr_name = obj.component.label
        self._attr_device_info = obj.get_info()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"update_{DOMAIN}_{self._obj.address}",
                self.async_write_ha_state,
            )
        )

    @property
    def brightness(self):
        return self._obj.get_value(self._obj.component.output)

    @property
    def is_on(self):
        return self.brightness > 0

    async def async_turn_on(self, **kwargs):
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        await self._obj.set_value(self._obj.component.output, brightness)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._obj.set_value(self._obj.component.output, 0)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._obj.available