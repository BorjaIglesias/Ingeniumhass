import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngThermostat
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate platform."""
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IngClimate(o) for o in api.get_climates()])

class IngClimate(ClimateEntity):
    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 0
    _attr_max_temp = 50

    def __init__(self, obj: IngThermostat):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
        self._attr_name = obj.component.label
        self._attr_device_info = obj.get_info()

    async def async_added_to_hass(self) -> None:
        """Register for updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, 
                f"update_{DOMAIN}_{self._obj.address}", 
                self.async_write_ha_state
            )
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current hvac mode."""
        return self._attr_hvac_modes[self._obj.get_mode()]

    @property
    def hvac_action(self) -> HVACAction:
        """Return current hvac action."""
        return [HVACAction.OFF, HVACAction.HEATING, HVACAction.COOLING][self._obj.get_action()]

    @property
    def current_temperature(self):
        """Return current temperature."""
        return self._obj.temp

    @property
    def target_temperature(self):
        """Return target temperature."""
        return self._obj.set_point

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new hvac mode."""
        await self._obj.set_mode(self._attr_hvac_modes.index(hvac_mode))
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            await self._obj.set_temp(temperature)
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return entity availability."""
        return self._obj.available