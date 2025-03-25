import asyncio
import datetime
import json
from collections import deque
from typing import Optional, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import IngSif, IngAirSensor, IngComponent, IngMeterBus, IngActuator, \
    IngBusingRegulator
import serial_asyncio

DOMAIN = "ingenium"

SIXLOWPAN_ENABLED = False
DEBUG = True
SERIAL_PORT = "/dev/ttyS6LP"

class SixLowPan:
    def __init__(self, hass: HomeAssistant, config: ConfigType):
        self.hass = hass
        self.config = config
        self.api: Optional[IngeniumAPI] = None
        self.write_queue: deque = deque(maxlen=256)
        self.serial_reader: Optional[asyncio.StreamReader] = None
        self.serial_writer: Optional[asyncio.StreamWriter] = None
        self.last_updates: Dict[str, datetime.datetime] = {}

    async def async_init(self, api: IngeniumAPI):
        self.api = api

        for o, c, i in api.get_sifs():
            c.add_update_notify(lambda _o=o, _c=c, _i=i: self.update_multisensor(_o, _c, _i))
        for o, c, i in api.get_meterbuses():
            c.add_update_notify(lambda _o=o, _c=c, _i=i: self.update_meterbus(_o, _c, _i))
        for o, c, i in api.get_air_sensors():
            c.add_update_notify(lambda _o=o, _c=c, _i=i: self.update_air_sensor(_o, _c, _i))
        for o, c in api.get_switches():
            c.add_update_notify(lambda _o=o, _c=c: self.update_actuator(_o, _c))
        for o, c in api.get_lights():
            c.add_update_notify(lambda _o=o, _c=c: self.update_dimmer(_o, _c))

        self.hass.loop.create_task(self.async_read_loop())
        self.hass.loop.create_task(self.async_write_loop())

    async def update_multisensor(self, obj: IngSif, comp: IngComponent, mode: int):
        modes_names = ["T", None, "P", "L", "H"]
        identifier = f"{DOMAIN}.{comp.id}_{modes_names[mode]}"
        name = f"{comp.label} {modes_names[mode]}"
        value = obj.get_value(mode)

        j = json.dumps({"type": "MUL", "id": identifier, "name": name, "value": value})
        await self.async_write_string(j)

    async def update_meterbus(self, obj: IngMeterBus, comp: IngComponent, channel: int):
        identifier = f"{DOMAIN}.{comp.id}_C{channel}"
        name = f"{comp.label} C{channel}"
        value = obj.get_cons(channel)

        j = json.dumps({"type": "MET", "id": identifier, "name": name, "value": value})
        await self.async_write_string(j)

    async def update_air_sensor(self, obj: IngAirSensor, comp: IngComponent, mode: int):
        measurements = ["CO2", "VOCs"]
        identifier = f"{DOMAIN}.{comp.id}_{measurements[mode].lower()}"
        name = f"{comp.label} {measurements[mode]}"
        value = obj.get_value(mode)

        j = json.dumps({"type": "AIR", "id": identifier, "name": name, "value": value})
        await self.async_write_string(j)

    async def update_actuator(self, obj: IngActuator, comp: IngComponent):
        identifier = f"{DOMAIN}.{comp.id}"
        name = comp.label
        is_on = obj.get_switch_val(comp)

        j = json.dumps({
            "type": "ACT", 
            "id": identifier, 
            "name": name, 
            "value": is_on, 
            "consumption": obj.consumption,
            "voltage": obj.voltage, 
            "current": obj.current, 
            "active_power": obj.active_power
        })
        await self.async_write_string(j)

    async def update_dimmer(self, obj: IngBusingRegulator, comp: IngComponent):
        identifier = f"{DOMAIN}.{comp.id}"
        name = comp.label
        value = obj.get_value(comp.output)

        j = json.dumps({"type": "DIM", "id": identifier, "name": name, "value": value})
        await self.async_write_string(j)

    async def async_write_string(self, data: str):
        if DEBUG:
            print(f"SEND {data}")
        self.write_queue.append((data + "\r\n").encode())

    async def async_read_loop(self):
        while True:
            try:
                if self.serial_reader is None:
                    self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                        url=SERIAL_PORT, baudrate=115200
                    )
                    print("# Serial Open #")

                line = await self.serial_reader.readline()
                if DEBUG:
                    print(f"READ {line.decode().strip()}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Exception in serial read loop: {e}")
                await asyncio.sleep(1)

    async def async_write_loop(self):
        while True:
            try:
                if self.serial_writer is None:
                    await asyncio.sleep(1)
                    continue

                if len(self.write_queue) == 0:
                    await asyncio.sleep(0.1)
                    continue

                item = self.write_queue.popleft()
                self.serial_writer.write(item)
                await self.serial_writer.drain()

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Exception in serial write loop: {e}")
                await asyncio.sleep(1)

if SIXLOWPAN_ENABLED:
    async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        six_low_pan = SixLowPan(hass, config)
        await six_low_pan.async_init(hass.data[DOMAIN]["api"])
        return True
