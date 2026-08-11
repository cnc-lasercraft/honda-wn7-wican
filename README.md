# Honda WN7 → Home Assistant (via WiCAN)

Live telemetry from the **Honda WN7 electric motorcycle** in Home Assistant,
using a [MeatPi WiCAN](https://github.com/meatpiHQ/wican-fw) OBD adapter and
MQTT. No cloud, no app — the data comes straight off the bike's CAN bus.

**What you get:**

| Sensor | Source | Status |
|---|---|---|
| State of charge (%, BMS + as displayed) | BMU (`0xD4` `A870`), cluster (`0xDE` `CFA2`) | ✅ verified vs. official diagnostic tool |
| Odometer (km) | Cluster (`0xDE`, DID `F012`) | ✅ verified, 0.1 km resolution |
| Pack voltage / current (V, signed A) | BMU (`0xD4`, DID `A870`) | ✅ verified; current sign under charge pending |
| Cell temperature, cell voltages min/max | BMU + cluster | ✅ verified |
| Battery SOH (%) | BMU (`0xD4`, DID `A870`) | ✅ verified |
| Charge cable connected | PCU (`0xCB`, DID `DB00`) | ✅ verified (plugged/unplugged) |
| Ambient + charge-port temperature (°C) | Cluster (`0xDE`, `CFA1`/`CFA2`) | ✅ verified |
| Range estimate (km) | derived (SOC × 1.4) | ✅ empirical |

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
the Home Assistant package handles the gaps.

## Setup

### 1. WiCAN

Two options:

- **Vehicle profile** — if "Honda: WN7" is available in your firmware's
  vehicle-profile list, select it and enable Home Assistant discovery. The
  profile source is in [`wican/honda_wn7.json`](wican/honda_wn7.json)
  (submitted upstream in [meatpiHQ/wican-fw#872](https://github.com/meatpiHQ/wican-fw/pull/872)).
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
- **Actively-charging state is partially decoded:** cable connected/unplugged
  is a clean flag (`0xCB DB00`), and the signed pack current goes negative
  while charging — but what the flag reports *during* an active session is
  not yet confirmed on this bike. If you charge from a connected wallbox, its
  integration remains the most reliable charging-state source.
- **Charge limit (max SOC) not yet located** — candidates identified, see the
  protocol notes.

## Repo layout

```
wican/honda_wn7.json            vehicle profile (for upstream wican-fw)
wican/manual-autopid-config.md  manual Automate-tab configuration
homeassistant/packages/         ready-to-use HA package
docs/obd-protocol.md            UDS/CAN findings, calibration, firmware quirks
docs/roadsync-ble.md            why the RoadSync BLE app is a telemetry dead end
```

## Contributing

Data points from other WN7s are very welcome — especially the `plug` value and
pack current **during an active charging session**, anything on the charge
limit (max SOC) setting, and observations from other markets/model years. Open
an issue with raw values and what the display showed.

## Disclaimer

Not affiliated with Honda or MeatPi. You are talking to your vehicle's ECUs at
your own risk. Read-only DID reads (service `0x22`) as documented here have
been used extensively without side effects, but no guarantees.

## License

[MIT](LICENSE)
