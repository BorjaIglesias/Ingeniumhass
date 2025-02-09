import datetime
import json
import time
from collections import deque
from threading import Thread
from typing import Optional, Dict

import logging
from serial import Serial

from ingeniumpy import IngeniumAPI
from ingeniumpy.objects import (
    IngSif,
    IngAirSensor,
    IngComponent,
    IngMeterBus,
    IngActuator,
    IngBusingRegulator,
)

# Actualizado para IngeniumAssistant
DOMAIN = "ingeniumassistant"

SIXLOWPAN_ENABLED = False
DEBUG = True
SERIAL_PORT = "/dev/ttyS6LP"

_LOGGER = logging.getLogger(__name__)


class SixLowPan:
    """
    Main 6LowPan communication class.

    Para cargarlo automáticamente, importa este módulo en
    custom_components/ingeniumassistant/__init__.py, después de la importación de IngeniumAPI.
    Ejemplo:

      from ingeniumpy import IngeniumAPI
      from .six_low_pan import SixLowPan

    Asegúrate de que en manifest.json se incluya la dependencia de pyserial:
      "requirements": [
        "ingeniumpy==1.0.0",
        "pyserial==3.5"
      ],

    Nota: Aunque Home Assistant soporta múltiples instancias para cada integración,
    este módulo 6LowPan utiliza una conexión serial exclusiva.
    """

    api: IngeniumAPI
    read_thread: Thread
    write_thread: Thread
    write_queue: deque = deque(maxlen=256)
    serial: Optional[Serial] = None
    last_updates: Dict[str, datetime.datetime] = {}

    def init(self, api: IngeniumAPI):
        """
        Se llama cuando se inicia la comunicación de la API de Ingenium y
        añade notificaciones para todos los dispositivos soportados.
        """
        self.api = api

        # Añadimos listeners de notificación para cada dispositivo
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

        # Hilos para lectura y escritura en la red 6LowPan
        self.read_thread = Thread(target=self.read_thread_loop, daemon=True)
        self.write_thread = Thread(target=self.write_thread_loop, daemon=True)
        self.read_thread.start()
        self.write_thread.start()

    #####################################################################################################
    # Funciones llamadas cuando se actualiza un dispositivo.
    #####################################################################################################

    def update_multisensor(self, obj: IngSif, comp: IngComponent, mode: int):
        modes_names = ["T", None, "P", "L", "H"]
        identifier = f"{DOMAIN}.{comp.id}_{modes_names[mode]}"
        name = f"{comp.label} {modes_names[mode]}"
        value = obj.get_value(mode)

        j = json.dumps({"type": "MUL", "id": identifier, "name": name, "value": value})
        self.write_string(j)

    def update_meterbus(self, obj: IngMeterBus, comp: IngComponent, channel: int):
        identifier = f"{DOMAIN}.{comp.id}_C{channel}"
        name = f"{comp.label} C{channel}"
        value = obj.get_cons(channel)

        j = json.dumps({"type": "MET", "id": identifier, "name": name, "value": value})
        self.write_string(j)

    def update_air_sensor(self, obj: IngAirSensor, comp: IngComponent, mode: int):
        measurements = ["CO2", "VOCs"]
        identifier = f"{DOMAIN}.{comp.id}_{measurements[mode].lower()}"
        name = f"{comp.label} {measurements[mode]}"
        value = obj.get_value(mode)

        j = json.dumps({"type": "AIR", "id": identifier, "name": name, "value": value})
        self.write_string(j)

    def update_actuator(self, obj: IngActuator, comp: IngComponent):
        identifier = f"{DOMAIN}.{comp.id}"
        name = comp.label
        is_on = obj.get_switch_val(comp)

        consumption = obj.consumption
        current = obj.current
        voltage = obj.voltage
        active_power = obj.active_power

        j = json.dumps({
            "type": "ACT",
            "id": identifier,
            "name": name,
            "value": is_on,
            "consumption": consumption,
            "voltage": voltage,
            "current": current,
            "active_power": active_power
        })
        self.write_string(j)

    def update_dimmer(self, obj: IngBusingRegulator, comp: IngComponent):
        identifier = f"{DOMAIN}.{comp.id}"
        name = comp.label
        value = obj.get_value(comp.output)

        j = json.dumps({"type": "DIM", "id": identifier, "name": name, "value": value})
        self.write_string(j)

    #####################################################################################################
    # Fin de las funciones de actualización.
    #####################################################################################################

    def write_string(self, data: str):
        if DEBUG:
            _LOGGER.debug("SEND %s", data)
        self.write_queue.append((data + "\r\n").encode())

    def read_thread_loop(self):
        line_bytes = bytearray()
        while True:
            try:
                if self.serial is None or not self.serial.is_open:
                    self.serial = Serial(port=SERIAL_PORT, baudrate=115200, timeout=None)
                    time.sleep(1)

                _LOGGER.debug("Serial Open")

                open_errors = 0
                while True:
                    if not self.serial or not self.serial.is_open:
                        _LOGGER.debug("Serial not open, retry")
                        time.sleep(2)
                        open_errors += 1
                        if open_errors >= 5:
                            break
                        continue

                    read = self.serial.read(size=1)
                    if read is None:
                        _LOGGER.debug("Serial read returned None")
                        break

                    line_bytes.extend(read)
                    if read in [b"\n", b"\r"]:
                        line = line_bytes.decode(errors="ignore")
                        line_bytes = bytearray()
                        if DEBUG:
                            _LOGGER.debug("READ %s", line)

                _LOGGER.debug("Serial is closed, reopening")

            except Exception as e:
                _LOGGER.error("Exception in serial read thread: %s", e)
                time.sleep(2)

    def write_thread_loop(self):
        while True:
            try:
                if self.serial is None or not self.serial.is_open:
                    time.sleep(1)

                if not self.write_queue:
                    time.sleep(0.1)
                    continue

                item = self.write_queue.popleft()
                self.serial.write(item)

            except Exception as e:
                _LOGGER.error("Exception in serial write thread: %s", e)
                time.sleep(1)


# Se ejecuta automáticamente cuando se importa, si SIXLOWPAN_ENABLED es True.
if SIXLOWPAN_ENABLED:
    IngeniumAPI.onload = lambda api: SixLowPan().init(api)
