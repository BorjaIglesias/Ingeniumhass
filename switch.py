import logging

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngActuator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    """Set up switch devices."""
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([IngSwitch(o) for o in api.get_switches()])


class IngSwitch(SwitchEntity):
    def __init__(self, obj: IngActuator):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
        self._attr_name = obj.component.label
        self._attr_device_class = (
            SwitchDeviceClass.OUTLET
            if obj.consumption != -1 or obj.voltage != -1
            else SwitchDeviceClass.SWITCH
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"update_{DOMAIN}_{self._obj.address}",
                self.async_write_ha_state
            )
        )

    @property
    def available(self) -> bool:
        return self._obj.available

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._obj.get_switch_val()

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._obj.action_switch()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._obj.action_switch()

    @property
    def extra_state_attributes(self):
        attrs = {}

        if self._obj.voltage == -1 and self._obj.consumption != -1:
            attrs["power"] = self._obj.consumption

        if self._obj.voltage != -1 and self._obj.current != -1:
            attrs["current"] = self._obj.current

        if self._obj.voltage != -1:
            attrs["voltage"] = self._obj.voltage

        if self._obj.active_power != -1:
            attrs["active_power"] = self._obj.active_power

        return attrs

    @property
    def device_info(self):
        return self._obj.get_info()
