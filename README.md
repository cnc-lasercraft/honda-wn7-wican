# Honda WN7 → Home Assistant (via WiCAN)

[![HACS](https://img.shields.io/badge/HACS-Integration-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/cnc-lasercraft/honda-wn7-wican/actions/workflows/validate.yml/badge.svg)](https://github.com/cnc-lasercraft/honda-wn7-wican/actions/workflows/validate.yml)

Live telemetry from the **Honda WN7 electric motorcycle** in Home Assistant,
using a [MeatPi WiCAN](https://github.com/meatpiHQ/wican-fw) OBD adapter and
MQTT. No cloud, no app — the data comes straight off the bike's CAN bus.

**What you get:**

| Sensor | Source | Status |
|---|---|---|
| State of charge (%, BMS + as displayed) | BMU (`0xD4` `A870`), cluster (`0xDE` `CFA2`) | ✅ verified vs. official diagnostic tool |
| Odometer (km) | Cluster (`0xDE`, DID `F012`) | ✅ verified, 0.1 km resolution |
| Pack voltage / current (V, signed A) + power (W) | BMU (`0xD4`, DID `A870`) | ✅ verified, negative current = charging |
| Cell temperature, cell voltages min/max | BMU + cluster | ✅ verified |
| Battery SOH (%) | BMU (`0xD4`, DID `A870`) | ✅ verified |
| Charge cable connected | PCU (`0xCB`, DID `DB00` `B15`) | ✅ verified (plugged/unplugged) |
| Charging (active) | PCU (`0xCB`, DID `DB00` `B14`) | ✅ verified during an AC session |
| Ambient + charge-port temperature (°C) | Cluster (`0xDE`, `CFA1`/`CFA2`) | ✅ verified |
| On-board charger temperature (°C) | OBC (`0xD0`, DID `CF03`) | ✅ verified against the diagnostic report |
| Range estimate (km) | derived (SOC × configurable km/%) | ✅ empirical |

Everything here was reverse-engineered on a single 2026 EU-market WN7 — nothing
in this repo is official. Byte positions were cross-checked against a passive
capture of **Honda's official MCS diagnostic tool** and its full-system report.
See the [protocol notes](docs/obd-protocol.md) for how the values were derived
and verified.

## Hardware

- Honda WN7 (2026)
- MeatPi WiCAN connected to the bike's diagnostic connector,
  firmware v4.21 or newer, joined to your Wi-Fi
- An MQTT broker reachable from that Wi-Fi (e.g. the Mosquitto add-on)

The bike powers the diagnostic port only while awake (ignition on or charging);
at key-off, bus and 12 V die within seconds. Sensors are therefore *windowed* —
they go `unavailable` once their value is stale instead of freezing at the last
reading.

## Setup

### 1. WiCAN

Two options:

- **Vehicle profile** — if "Honda: WN7" is available in your firmware's
  vehicle-profile list, select it and enable Home Assistant discovery. The
  profile source is in [`wican/honda_wn7.json`](wican/honda_wn7.json)
  (submitted upstream in [meatpiHQ/wican-fw#872](https://github.com/meatpiHQ/wican-fw/pull/872)).
- **Manual AutoPID config** — follow
  [`wican/manual-autopid-config.md`](wican/manual-autopid-config.md). This is
  what the Home Assistant integration below expects (topics
  `wican/honda_wn7/<name>`). It also covers the firmware traps —
  **read the warnings before you start**, one of them boot-loops the device.

### 2. Home Assistant

#### Option A — the integration (recommended)

Install via [HACS](https://hacs.xyz):

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cnc-lasercraft&repository=honda-wn7-wican&category=integration)

Or manually: copy `custom_components/honda_wn7/` into your `<config>/custom_components/`.

Restart Home Assistant, then **Settings → Devices & Services → Add Integration
→ Honda WN7**. It asks for the MQTT topic prefix (default `wican/honda_wn7`),
the km-per-percent factor for the range estimate, and whether your WiCAN
expressions are *scaled* (as documented above) or *raw* register reads — see
[both expression styles](wican/manual-autopid-config.md#two-ways-to-write-the-expressions).
It then creates one device with all sensors: garbage filtering,
signed-current conversion, battery power and staleness handling included.
Both settings can be changed later under *Configure*.

Requires the MQTT integration to be set up; nothing has to be added to
`configuration.yaml`.

#### Option B — the YAML package

If you would rather not run a custom integration, copy
[`homeassistant/packages/honda_wn7.yaml`](homeassistant/packages/honda_wn7.yaml)
into `<config>/packages/` (enable packages first) and restart. Same sensors,
built from `mqtt:` and `template:` entries. Do not run both at once.

## Known limitations

- **Trip meters A/B cannot be read** — they only exist inside the cluster.
  Use a `utility_meter` helper on the odometer sensor instead.
- **No wake/sleep distinction from outside:** a sleeping bike at home and a
  bike that rode away look identical (Wi-Fi + MQTT just stop). If you need
  presence, correlate with something else (garage door, GPS tracker).
- **SOC staleness after a ride:** if the bike sleeps immediately after a trip,
  the dashboard keeps the pre-trip SOC until the next wake window. The BMS
  value itself is accurate under load.
- **Charge limit (max SOC) not yet located** — the register was not found even
  during a limited charging session, and bus plus 12 V die essentially *with*
  the end of charging. Infer it from "charging ended below 100 %" instead; see
  the protocol notes.

## Repo layout

```
custom_components/honda_wn7/    Home Assistant integration (HACS)
wican/honda_wn7.json            vehicle profile (for upstream wican-fw)
wican/manual-autopid-config.md  manual Automate-tab configuration
homeassistant/packages/         YAML package alternative to the integration
docs/obd-protocol.md            UDS/CAN findings, calibration, firmware quirks
docs/roadsync-ble.md            why the RoadSync BLE app is a telemetry dead end
```

## Contributing

Data points from other WN7s are very welcome — especially anything on the
charge limit (max SOC) setting, and observations from other markets/model
years. Open an issue with raw values and what the display showed; the
integration's *Download diagnostics* button dumps every topic it has seen.

## Disclaimer

Not affiliated with Honda or MeatPi. You are talking to your vehicle's ECUs at
your own risk. Read-only DID reads (service `0x22`) as documented here have
been used extensively without side effects, but no guarantees.

## License

[MIT](LICENSE)
