# Honda WN7 → Home Assistant (via WiCAN)

Live telemetry from the **Honda WN7 electric motorcycle** in Home Assistant,
using a [MeatPi WiCAN](https://github.com/meatpiHQ/wican-fw) OBD adapter and
MQTT. No cloud, no app — the data comes straight off the bike's CAN bus.

**What you get:**

| Sensor | Source | Status |
|---|---|---|
| State of charge (%) | BMS (`0xD4`, DID `A870`) | ✅ verified 15–100 %, ±2.5 % vs. display |
| Odometer (km) | Cluster (`0xDE`, DID `F012`) | ✅ verified, 0.1 km resolution |
| Range estimate (km) | derived (SOC × 1.4) | ✅ empirical |
| Battery temperature (°C) | Charger (`0xD0`, DID `CF03`) | 🧪 experimental |

Everything here was reverse-engineered on a single 2026 EU-market WN7 — nothing
in this repo is official. See the [protocol notes](docs/obd-protocol.md) for
how the values were derived and verified.

## Hardware

- Honda WN7 (2026)
- MeatPi WiCAN connected to the bike's diagnostic connector,
  firmware v4.21 or newer, joined to your Wi-Fi
- An MQTT broker reachable from that Wi-Fi (e.g. the Mosquitto add-on)

The bike powers the diagnostic port only while awake (ignition on or charging);
at key-off, bus and 12 V die within seconds. Sensors are therefore *windowed* —
the Home Assistant package handles the gaps.

## Setup

### 1. WiCAN

Two options:

- **Vehicle profile** — if "Honda: WN7" is available in your firmware's
  vehicle-profile list, select it and enable Home Assistant discovery. The
  profile source is in [`wican/honda_wn7.json`](wican/honda_wn7.json).
- **Manual AutoPID config** — follow
  [`wican/manual-autopid-config.md`](wican/manual-autopid-config.md)
  (also covers the experimental temperature PID and the firmware traps —
  **read the warnings before you start**, one of them boot-loops the device).

### 2. Home Assistant

Copy [`homeassistant/packages/honda_wn7.yaml`](homeassistant/packages/honda_wn7.yaml)
into `<config>/packages/` (enable packages if you haven't), adjust the MQTT
topic prefix if needed, restart. You get raw sensors plus cleaned/derived
ones (garbage filtering, SOC cap, range estimate).

## Known limitations

- **Trip meters A/B cannot be read** — they only exist inside the cluster.
  Use a `utility_meter` helper on the odometer sensor instead.
- **No wake/sleep distinction from outside:** a sleeping bike at home and a
  bike that rode away look identical (Wi-Fi + MQTT just stop). If you need
  presence, correlate with something else (garage door, GPS tracker).
- **SOC staleness after a ride:** if the bike sleeps immediately after a trip,
  the dashboard keeps the pre-trip SOC until the next wake window. The BMS
  value itself is accurate under load.
- **Charging state:** there is no usable charging flag on the diagnostic side
  (the obvious candidate turned out to be a temperature). If you charge from a
  connected wallbox, derive charging state from the wallbox integration.

## Repo layout

```
wican/honda_wn7.json            vehicle profile (for upstream wican-fw)
wican/manual-autopid-config.md  manual Automate-tab configuration
homeassistant/packages/         ready-to-use HA package
docs/obd-protocol.md            UDS/CAN findings, calibration, firmware quirks
docs/roadsync-ble.md            why the RoadSync BLE app is a telemetry dead end
```

## Contributing

Data points from other WN7s are very welcome — especially SOC field ↔ display
pairs (mid-range 40–70 % is thin), temperature-byte observations, and anything
from other markets/model years. Open an issue with raw values and what the
display showed.

## Disclaimer

Not affiliated with Honda or MeatPi. You are talking to your vehicle's ECUs at
your own risk. Read-only DID reads (service `0x22`) as documented here have
been used extensively without side effects, but no guarantees.

## License

[MIT](LICENSE)
