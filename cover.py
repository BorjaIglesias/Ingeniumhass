import logging
from homeassistant.components.cover import CoverEntity, CoverDeviceClass, ATTR_POSITION
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngActuator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IngCover(o) for o in api.get_covers()])

class IngCover(CoverEntity):
    def __init__(self, obj: IngActuator):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
        self._attr_name = obj.component.label
        self._attr_device_class = CoverDeviceClass.BLIND

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.available

    @property
    def current_cover_position(self):
        return self._obj.get_cover_val()

    @property
    def is_closed(self):
        return self._obj.get_cover_val() == 0

    async def async_open_cover(self, **kwargs):
        await self._obj.set_cover_val(100)
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        await self._obj.set_cover_val(0)
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs):
        await self._obj.set_cover_val(kwargs[ATTR_POSITION])
        self.async_write_ha_state()

    @property
    def device_info(self):
        return self._obj.get_info()
