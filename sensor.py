import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPower,
    UnitOfTemperature,
    CONCENTRATION_PARTS_PER_MILLION,
    SIGNAL_STRENGTH_DECIBELS,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfApparentPower,
)
from homeassistant.core import HomeAssistant
from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import (
    IngMeterBus,
    IngSif,
    IngAirSensor, IngActuator, IngNoiseSensor
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    api: IngeniumAPI = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([MeterBusSensor(o, i) for o, i in api.get_meterbuses()])
    async_add_entities([SifSensor(o, i) for o, i in api.get_sifs()])
    async_add_entities([AirSensor(o, i) for o, i in api.get_air_sensors()])
    async_add_entities([NoiseSensor(o) for o in api.get_noise_sensors()])
    async_add_entities([SockSensor(o, i) for o in api.get_switches() if o.is_sock for i in range(4)])

class MeterBusSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngMeterBus, channel: int):
        self._obj = obj
        self._channel = channel
        self._attr_name = f"{obj.component.label} C{self._channel}"
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_C{channel}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._channel)

    @property
    def native_value(self):
        return self._obj.get_value(self._channel)

    @property
    def device_info(self):
        return self._obj.get_info()

class SifSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngSif, mode: int):
        self._obj = obj
        self._mode = mode
        modes_names = ["T", "S", "P", "L", "H"]
        self._attr_name = f"{obj.component.label} {modes_names[mode]}"
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{modes_names[mode]}"
        
        if mode == 0:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif mode == 3:
            self._attr_device_class = SensorDeviceClass.ILLUMINANCE
            self._attr_native_unit_of_measurement = "lx"
        elif mode == 4:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._mode)

    @property
    def native_value(self):
        return self._obj.get_value(self._mode)

    @property
    def extra_state_attributes(self):
        return {"bat_baja": True} if self._obj.bat_baja else {}

    @property
    def device_info(self):
        return self._obj.get_info()

class AirSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngAirSensor, mode: int):
        self._obj = obj
        self._mode = mode
        modes = ["CO2", "VOCs", "Temp", "Hum"]
        self._attr_name = f"{obj.component.label} {modes[mode]}"
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{modes[mode].lower()}"
        
        if mode == 0:
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        elif mode == 1:
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        elif mode == 2:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif mode == 3:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.get_available(self._mode)

    @property
    def native_value(self):
        return self._obj.get_value(self._mode)

    @property
    def extra_state_attributes(self):
        if self._mode in [0, 1]:
            return {"threshold": self._obj.get_threshold(self._mode)}
        return {}

    @property
    def device_info(self):
        return self._obj.get_info()

class NoiseSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS

    def __init__(self, obj: IngNoiseSensor):
        self._obj = obj
        self._attr_name = obj.component.label
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.get_available()

    @property
    def native_value(self):
        return self._obj.get_value()

    @property
    def extra_state_attributes(self):
        attrs = {}
        if self._obj.max != 255:
            attrs["max"] = self._obj.max
        if self._obj.min != 255:
            attrs["min"] = self._obj.min
        return attrs

    @property
    def device_info(self):
        return self._obj.get_info()

class SockSensor(SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, obj: IngActuator, mode: int):
        self._obj = obj
        self._mode = mode
        modes_names = ["I", "V", "PA", "P"]
        self._attr_name = f"{obj.component.label} {modes_names[mode]}"
        self._attr_unique_id = f"{DOMAIN}.{obj.component.id}_{modes_names[mode]}"
        
        if mode == 0:
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        elif mode == 1:
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        elif mode == 2:
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
        elif mode == 3:
            self._attr_native_unit_of_measurement = UnitOfApparentPower.VOLT_AMPERE

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"update_{DOMAIN}_{self._obj.address}", self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return self._obj.available

    @property
    def native_value(self):
        values = [self._obj.current, self._obj.voltage, self._obj.active_power, self._obj.consumption]
        return values[self._mode] if values[self._mode] != -1 else None

    @property
    def device_info(self):
        return self._obj.get_info()