Ingenium Integration for Home Assistant
This custom integration allows you to control and monitor Ingenium devices in Home Assistant.

Features
Support for various Ingenium devices:

Multisensors (temperature, presence, illuminance, humidity)

Meter buses

Air sensors (CO2, VOCs)

Switches and actuators

Dimmers and lights

Optional 6LowPan communication support

Installation
Copy the ingenium folder to your custom_components directory in Home Assistant.

Add the following to your configuration.yaml:
Restart Home Assistant.
Go to Configuration > Integrations and click "Add Integration".
Search for "Ingenium" and follow the setup process.

Configuration
The integration supports two modes:

Remote: Requires username and password
Local: Requires the host IP address

6LowPan Support (Optional)
To enable 6LowPan communication:

Ensure pyserial is installed:

json
"requirements": [
  "ingeniumpy==0.7.2",
  "pyserial==3.5"
]
Set SIXLOWPAN_ENABLED = True in six_low_pan.py.

Configure the serial port in six_low_pan.py:

python
SERIAL_PORT = "/dev/ttyS6LP"
Troubleshooting
Check Home Assistant logs for any errors related to the Ingenium integration.

Ensure your Ingenium devices are properly connected and configured.

Contributing
Contributions are welcome! Please submit pull requests or open issues on the GitHub repository.
