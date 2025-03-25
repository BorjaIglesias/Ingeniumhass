iimport logging
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    UnitOfTemperature,
)
from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngThermostat

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([IngClimate(o) for o in api.get_climates()])

class IngClimate(ClimateEntity):
    def __init__(self, obj: IngThermostat):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
        self._attr_name = obj.component.label
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = 0.2
        self._attr_max_temp = 51
        self._attr_min_temp = 0
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    async def async_added_to_hass(self) -> None:
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
    def current_temperature(self):
        return self._obj.temp

    @property
    def target_temperature(self):
        return self._obj.set_point

    @property
    def hvac_mode(self) -> HVACMode:
        return self._attr_hvac_modes[self._obj.get_mode()]

    @property
    def hvac_action(self) -> HVACAction:
        return [HVACAction.OFF, HVACAction.HEATING, HVACAction.COOLING][self._obj.get_action()]

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._obj.set_mode(self._attr_hvac_modes.index(hvac_mode))
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs) -> None:
        await self._obj.set_temp(kwargs[ATTR_TEMPERATURE])
        self.async_write_ha_state()

    @property
    def device_info(self):
        return self._obj.get_info()
