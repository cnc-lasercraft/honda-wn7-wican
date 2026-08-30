# Manual WiCAN AutoPID configuration (Automate tab)

Use this if you prefer manual MQTT topics over the vehicle profile / HA discovery,
or if the Honda WN7 profile is not yet available in your firmware's profile list.

Tested on WiCAN firmware **v4.21** with a 2026 Honda WN7. All byte positions were
verified against Honda's official MCS diagnostic tool (passive capture + report
matching) — see [docs/obd-protocol.md](../docs/obd-protocol.md).

> ⚠️ **Configure ONLY through the web UI (Automate tab).** Do not POST raw JSON to
> `/store_config` / `/store_auto_data`: the firmware parses all config values as
> strings — a bare number in hand-crafted JSON crashes the config parser and
> boot-loops the device **before Wi-Fi starts** (recovery then requires USB
> re-flash). The web UI always writes strings and is safe.

> ⚠️ **New or changed PIDs only take effect after a device reboot** (System tab).
> "Store" + "Submit" alone is not enough — the AutoPID task loads its list at boot.

> ⚠️ **Expression syntax trap:** the bracket syntax only accepts *ranges*.
> `[B14]` is silently invalid (no value is ever published). For a single byte
> write `[B14:B14]` or the bare form `B14`.

## Global settings

| Field | Value |
|---|---|
| Initialisation | `ATSP7;ATST96;` |
| Vehicle Model (Car Specific) | disable |
| Standard PIDs | disable |
| Grouping | disable |
| Cycle | 5000 |

Protocol: `auto_pid`. MQTT must be enabled and pointed at your broker.

## PID list

Type is always `MQTT_Topic`, topic `wican/honda_wn7/<name>`. Pick the subset you
care about — every entry is polled on its own period, so more entries means more
bus traffic (all of these together are still fine).

| Name | Init | PID | Expression | Period | Value |
|---|---|---|---|---|---|
| `soc` | `ATSHDAD4F1;` | `22A8709` | `[B52:B53]*0.01` | 10000 | BMS "In-Fact" SOC, % |
| `pack_v` | `ATSHDAD4F1;` | `22A8709` | `[B19:B20]*0.1` | 10000 | pack voltage, V (~392 nominal) |
| `pack_i` | `ATSHDAD4F1;` | `22A8709` | `[B21:B22]` | 10000 | pack current, **raw** — see note |
| `batt_temp` | `ATSHDAD4F1;` | `22A8709` | `B47-40` | 30000 | max cell temperature, °C |
| `soh` | `ATSHDAD4F1;` | `22A8709` | `B61` | 60000 | battery SOH, % |
| `odometer` | `ATSHDADEF1;` | `22F0122` | `[B6:B7]*6553.6+[B9:B10]*0.1` | 30000 | odometer, km |
| `soc_disp` | `ATSHDADEF1;` | `22CFA29` | `B39` | 20000 | SOC exactly as the TFT shows it, integer % |
| `ambient` | `ATSHDADEF1;` | `22CFA29` | `B26` | 60000 | ambient temperature, °C (no offset) |
| `cell_max` | `ATSHDADEF1;` | `22CFA29` | `[B41:B42]/5` | 60000 | highest cell voltage, mV |
| `cell_min` | `ATSHDADEF1;` | `22CFA29` | `[B43:B44]/5` | 60000 | lowest cell voltage, mV |
| `port_temp` | `ATSHDADEF1;` | `22CFA19` | `B26-40` | 60000 | AC charge-port temperature, °C |
| `plug` | `ATSHDACBF1;` | `22DB009` | `B15` | 10000 | `1` = no cable, `3` = cable plugged in |
| `charge_state` | `ATSHDACBF1;` | `22DB009` | `B14` | 10000 | `1` = not charging, `2` = charging |

Notes:

- **`soc` vs `soc_disp`:** `soc` is the BMS's own SOC with 0.01 % resolution;
  `soc_disp` is the integer the cluster renders. They track each other within
  ~1 %. An older approach calibrated a remaining-energy field
  (`[B59:B60]*0.11266+2.457`) against the display — it drifts in the midrange,
  prefer the direct fields.
- **`pack_i` is a signed 16-bit value** published raw here (values near 65535
  = small negative currents; negative = charging). Convert downstream:
  `value > 32767 ? (value - 65536)/10 : value/10` A — the HA package does this.
  (Newer firmwares also accept signed-byte syntax `((S21*256)+B22)*0.1`
  directly in the expression; the raw variant works everywhere.)
- **`plug` and `charge_state` belong together.** `plug` stays at `3` during an
  active charge — there is no separate "charging" value in that byte. The
  charge-active flag is the neighbouring byte `charge_state` (`1` = not
  charging even with the cable in, `2` = charging), verified during a real AC
  session. Full state: `plug=1` unplugged · `plug=3, charge_state=1` plugged
  and idle · `plug=3, charge_state=2` charging.
- The odometer expression is split in two ranges because the value spans an
  ISO-TP frame boundary (PCI bytes are part of WiCAN's byte indexing — see the
  protocol doc).

## Verification

- `http://<wican-ip>/autopid_data` shows the last polled values, e.g.
  `{"soc":85.13,"soc_disp":85,"odometer":465.8,"pack_v":392.5,...}`.
- Compare `soc_disp` against the TFT display — it should match exactly;
  `soc` should be within ~1 %.
- The bike must be awake (ignition on or actively charging) — when it sleeps,
  the whole CAN bus and 12 V supply are cut within ~4 s and WiCAN goes offline.
