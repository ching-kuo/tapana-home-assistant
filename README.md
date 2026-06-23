# Sony LGTG Multifunctional Light — Home Assistant Integration

A Home Assistant custom integration for the Sony LGTG-100 and LGTG-200 Multifunctional Light devices. It communicates with the Tapana cloud API (the same backend used by the Tapana/MFlight mobile app) to control the light and read environmental sensor data.

## Supported Devices

- Sony LGTG-100 Multifunctional Light
- Sony LGTG-200 Multifunctional Light

## Features

The integration exposes the following entities for each configured device:

| Entity | Type | Device Class | Unit |
|---|---|---|---|
| Light | `light` | — | — |
| Temperature | `sensor` | `temperature` | C |
| Humidity | `sensor` | `humidity` | % |
| Illuminance | `sensor` | `illuminance` | lx |
| Presence | `binary_sensor` | `motion` | — |
| Connected | `binary_sensor` | `connectivity` | — |

Light capabilities:
- On/off control
- Brightness adjustment (0–100%)
- Color temperature (2700 K warm to 6500 K cool)

State is polled from the cloud every 30 seconds.

## Prerequisites

- A Tapana account (register via the Tapana or MFlight mobile app)
- Your device's node ID (a numeric identifier — see [Finding Your Node ID](#finding-your-node-id))
- Home Assistant 2024.1 or newer
- Python 3.11 or newer

## Installation

### Manual (works for private or local-only copies)

1. Copy the `custom_components/sony_tapana/` directory into the `custom_components/` directory of your Home Assistant configuration folder.

   ```
   <config>/
     custom_components/
       sony_tapana/   <-- place the directory here
   ```

2. Restart Home Assistant. The required Python packages (`pycognito`, `boto3`)
   are declared in `manifest.json` and installed automatically on first load.

### HACS

1. In Home Assistant, open **HACS**.
2. Click the three-dot menu (top right) > **Custom repositories**.
3. Add `https://github.com/ching-kuo/tapana-home-assistant` with category
   **Integration**, then click **Add**.
4. Search for **Sony LGTG**, click **Download**, and restart Home Assistant.

## Configuration

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration**.
3. Search for **Sony LGTG**.
4. Enter your Tapana account email and password, then click **Submit**.
5. The integration authenticates and lists the devices on your account. Pick
   your light from the dropdown and click **Submit**.

The integration then begins polling the selected device. No node ID lookup is
required -- devices are discovered automatically from your account.

## Entities

| Entity ID suffix | Platform | Device class | Unit | Notes |
|---|---|---|---|---|
| (device name) | `light` | — | — | On/off, brightness 0–255, color temp 2700–6500 K |
| `_temperature` | `sensor` | `temperature` | C | Range -30 to 50 C |
| `_humidity` | `sensor` | `humidity` | % | Range 0–100% |
| `_illuminance` | `sensor` | `illuminance` | lx | Ambient light level |
| `_presence` | `binary_sensor` | `motion` | — | True when motion is detected |
| `_connected` | `binary_sensor` | `connectivity` | — | True when device is online |

## Project Structure

```
hacs.json                HACS metadata
custom_components/sony_tapana/
    __init__.py          Integration setup and teardown
    binary_sensor.py     Presence and connectivity binary sensors
    config_flow.py       UI-based configuration flow
    const.py             HA-specific constants
    coordinator.py       DataUpdateCoordinator (30 s polling)
    light.py             Light entity with color temperature support
    manifest.json        Integration metadata
    sensor.py            Temperature, humidity, illuminance sensors
    strings.json         Config flow localization strings
    tapana_client/       Embedded Tapana cloud API client
        __init__.py
        client.py        TapanaClient: authentication and GraphQL requests
        const.py         AWS endpoints, sensor type IDs, command constants
        exceptions.py    Error hierarchy
        models.py        Data models: LightState, SensorData, Node
    translations/
        en.json          English UI translations
```

## License

This project is not affiliated with or endorsed by Sony Group Corporation.
