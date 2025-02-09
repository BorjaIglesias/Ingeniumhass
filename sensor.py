import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfPower,
    UnitOfTemperature,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfApparentPower,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import (
    IngMeterBus,
    IngSif,
    IngAirSensor,
    IngActuator,
    IngNoiseSensor,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    entities.extend(MeterBusSensor(obj, channel) for obj, channel in api.get_meterbuses())
    entities.extend(SifSensor(obj, mode) for obj, mode in api.get_sifs())
    entities.extend(AirSensor(obj, mode) for obj, mode in api.get_air_sensors())
    entities.extend(NoiseSensor(obj) for obj in api.get_noise_sensors())
    entities.extend(
        SockSensor(obj, mode)
        for mode in range(4)
        for obj in api.get_switches()
        if obj.is_sock
    )
    
    async_add_entities(entities)

class MeterBusSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, obj: IngMeterBus, channel: int):
        self._obj = obj
        self._channel = channel
        self._attr_name = f"C{channel}"
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_C{channel}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
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
    def native_value(self):
        return self._obj.get_value(self._channel)

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._channel)

class SifSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, obj: IngSif, mode: int):
        self._obj = obj
        self._mode = mode
        modes_names = ["T", "S", "P", "L", "H"]
        
        self._attr_name = modes_names[mode]
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{modes_names[mode]}"
        self._attr_device_info = obj.get_info()
        self._attr_state_class = SensorStateClass.MEASUREMENT

        if mode == 0:
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif mode == 2:
            self._attr_device_class = SensorDeviceClass.OCCUPANCY
        elif mode == 3:
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
            self._attr_native_unit_of_measurement = "lx"
        elif mode == 4:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"update_{DOMAIN}_{self._obj.address}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self):
        return self._obj.get_value(self._mode)

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._mode)

    @property
    def extra_state_attributes(self):
        return {"bat_baja": True} if self._obj.bat_baja else {}

class AirSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngAirSensor, mode: int):
        self._obj = obj
        self._mode = mode
        mode_data = {
            0: ("CO2", SensorDeviceClass.CO2, CONCENTRATION_PARTS_PER_MILLION),
            1: ("VOCs", None, CONCENTRATION_PARTS_PER_MILLION),
            2: ("Temp", SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS),
            3: ("Hum", SensorDeviceClass.HUMIDITY, PERCENTAGE),
        }
        
        name_suffix, device_class, unit = mode_data[mode]
        self._attr_name = name_suffix
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{name_suffix.lower()}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
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
    def native_value(self):
        return self._obj.get_value(self._mode)

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._mode)

    @property
    def extra_state_attributes(self):
        return {"threshold": self._obj.get_threshold(self._mode)} if self._mode in (0, 1) else {}

class NoiseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngNoiseSensor):
        self._obj = obj
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"
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
    def native_value(self):
        return self._obj.get_value()

    @property
    def available(self) -> bool:
        return self._obj.get_available()

    @property
    def extra_state_attributes(self):
        return {
            "max": self._obj.max,
            "min": self._obj.min,
        } if self._obj.max != 255 or self._obj.min != 255 else {}

class SockSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngActuator, mode: int):
        self._obj = obj
        self._mode = mode
        mode_config = {
            0: ("I", SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
            1: ("V", SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
            2: ("PA", SensorDeviceClass.POWER, UnitOfPower.WATT),
            3: ("P", SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE),
        }
        
        suffix, device_class, unit = mode_config[mode]
        self._attr_name = suffix
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{suffix}"
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
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
    def native_value(self):
        return {
            0: self._obj.current,
            1: self._obj.voltage,
            2: self._obj.active_power,
            3: self._obj.consumption,
        }[self._mode]

    @property
    def available(self) -> bool:
        return self._obj.available