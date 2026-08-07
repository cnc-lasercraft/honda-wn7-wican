# Manual WiCAN AutoPID configuration (Automate tab)

Use this if you prefer manual MQTT topics over the vehicle profile / HA discovery,
or if the Honda WN7 profile is not yet available in your firmware's profile list.

Tested on WiCAN firmware **v4.21** with a 2026 Honda WN7.

> ⚠️ **Configure ONLY through the web UI (Automate tab).** Do not POST raw JSON to
> `/store_config` / `/store_auto_data`: the firmware parses all config values as
> strings — a bare number in hand-crafted JSON crashes the config parser and
> boot-loops the device **before Wi-Fi starts** (recovery then requires USB
> re-flash). The web UI always writes strings and is safe.

> ⚠️ **New or changed PIDs only take effect after a device reboot** (System tab).
> "Store" + "Submit" alone is not enough — the AutoPID task loads its list at boot.

## Global settings

| Field | Value |
|---|---|
| Initialisation | `ATSP7;ATST96;` |
| Vehicle Model (Car Specific) | disable |
| Standard PIDs | disable |
| Grouping | disable |
| Cycle | 5000 |

Protocol: `auto_pid`. MQTT must be enabled and pointed at your broker.

## PID 1 — State of charge (ECU 0xD4 = BMS)

| Field | Value |
|---|---|
| Name | `soc` |
| Init | `ATSHDAD4F1;` |
| PID | `22A8709` |
| Expression | `[B59:B60]*0.11266+2.457` |
| Period | 10000 |
| Type | MQTT_Topic |
| Send_to | `wican/honda_wn7/soc` |

The trailing `9` in the PID is the expected-frame count (`22 A870` + "expect 9
frames"). The response is a 56-byte block; bytes 47–48 of the payload hold a
remaining-energy field that maps linearly to the displayed SOC (see
[docs/obd-protocol.md](../docs/obd-protocol.md) for the calibration data).

## PID 2 — Odometer (ECU 0xDE = meter/cluster)

| Field | Value |
|---|---|
| Name | `odometer` |
| Init | `ATSHDADEF1;` |
| PID | `22F0122` |
| Expression | `[B6:B7]*6553.6+[B9:B10]*0.1` |
| Period | 30000 |
| Type | MQTT_Topic |
| Send_to | `wican/honda_wn7/odometer` |

32-bit value, 0.1 km resolution. The two-range expression is needed because the
value spans a first frame / consecutive frame boundary (ISO-TP PCI bytes are
part of WiCAN's byte indexing — see protocol doc).

## PID 3 — Battery/charger temperature (ECU 0xD0) — EXPERIMENTAL

| Field | Value |
|---|---|
| Name | `temp_raw` |
| Init | `ATSHDAD0F1;` |
| PID | `22CF039` |
| Expression | `[B14:B14]` |
| Period | 15000 |
| Type | MQTT_Topic |
| Send_to | `wican/honda_wn7/temp_raw` |

Temperature in °C is `value − 40` (standard OBD offset). The interpretation as a
temperature fits all observations so far (cold morning ≈ 25 °C, after ride +
charge ≈ 46–49 °C) but has not been fully cross-verified — treat as experimental.
It is **not** a charging flag (an earlier hypothesis, disproven).

> ⚠️ **Expression syntax trap:** the bracket syntax only accepts *ranges*.
> `[B14]` is silently invalid (no value is ever published). For a single byte
> write `[B14:B14]` or the bare form `B14`.

## Verification

- `http://<wican-ip>/autopid_data` shows the last polled values, e.g.
  `{"soc":89.32,"odometer":193.2,"temp_raw":65}`.
- Compare SOC against the TFT display (should match within ~±2.5 %).
- The bike must be awake (ignition on or actively charging) — when it sleeps,
  the whole CAN bus and 12 V supply are cut within ~4 s and WiCAN goes offline.
