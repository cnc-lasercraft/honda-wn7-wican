# Honda WN7 — OBD/UDS protocol notes

Reverse-engineered on a 2026 Honda WN7 (electric motorcycle, EU market) using a
MeatPi WiCAN on the diagnostic connector. Everything below was observed on one
bike — expect variations between markets and model years, and verify against
your TFT display before trusting any value.

## Bus & addressing

- CAN 500 kbit/s, **29-bit extended addressing** (ISO 15765-4, `ATSP7`).
- UDS requests go to `18DA<ECU>F1`, responses come from `18DAF1<ECU>`
  (default priority byte `0x18`). With WiCAN/ELM327 this means:
  `ATSHDAD4F1;` is all you need — the default RX filter (`18DAF1xx`) and
  automatic flow control already do the right thing. No `ATCRA`/`ATFCSH`
  gymnastics required.
- Idle bus traffic while awake: heartbeat frames `0x790` (~102/s) and
  `0x605` (~10/s), both all-zero payloads.

## Known ECUs

| Address | Unit |
|---|---|
| `0xD4` | BMS (battery management) |
| `0xDE` | Meter / instrument cluster |
| `0xD0` | Charger / power unit |

Two further ECUs respond to TesterPresent but have not been mapped.

## Useful DIDs (service 0x22)

### `0xD4` (BMS) — DID `A870`: battery status block

56-byte payload. Bytes 47–48 (0-based, after the `62 A8 70` header) hold a
16-bit **remaining-energy field** that maps linearly to the SOC shown on the
display:

```
SOC % = field × 0.11266 + 2.457
```

Calibration points (field ↔ display): 115 ↔ 15 %, 251 ↔ 32 %, 831 ↔ 81 %,
868 ↔ 100 %. Verified across 15–100 % on multiple charge sessions; the
formula tracks the display within ~±2.5 %.

**Staleness caveat:** the field is a BMS estimate. It refreshes reliably under
load (riding, charging). A value read right after wake-up following a long
park can still be the pre-park estimate.

### `0xD4` — DIDs `A820`–`A82A`, `DA5C`, `DA5F`

Event/error counter blocks (present, not decoded).

### `0xDE` (meter) — DID `F012`: odometer

Response `62 F0 12 <u32>`; 32-bit value in 0.1 km. Matches the display exactly.

### `0xDE` — DIDs `D300`–`D30A`: battery SOH blocks

One block per cell unit, pattern `00 00 64 xx xx` = SOH 100 % plus a capacity
value (695 / 631 observed on a new bike).

### `0xD0` (charger) — DID `CF03`: status block

- Payload byte 8 (after `62 CF 03`) is almost certainly a **temperature**
  with the standard OBD −40 offset: cold morning → 65 (25 °C), after ride +
  charge → 86–89 (46–49 °C). It rises slowly and continuously.
  **It is NOT a charging flag** — an earlier "0x58 = charging" hypothesis was
  disproven (the correlation was just warm-while-charging).
- Bytes 9–14 contain a value repeated three times: ~858 while charging,
  690 idle. Candidate: battery voltage × 0.1. Undecoded.

## Negative results (save yourself the time)

- **Trip meters A/B are not readable.** 49 DIDs across all ECUs were dumped
  while the display showed known trip values — no match. Trips (and SOC %)
  are rendered only inside the cluster. Workaround: a `utility_meter` helper
  on the odometer sensor.
- **The displayed range estimate is unreliable** (showed 243 km where ~140 km
  is physically possible). Better: SOC × 1.4 km/% (empirical, ~140 km at
  100 %, matches the factory figure).
- **There is no shutdown announcement.** At key-off the whole bus and the 12 V
  supply die within ~4 s, mid-heartbeat, with no special frames. From the
  outside, "parked and sleeping" and "ridden away" look identical. (The
  DC/DC does keep running for a few minutes after a *charging* session ends —
  that is a different path.)
- **RoadSync BLE carries no battery data** — see
  [roadsync-ble.md](roadsync-ble.md).

## WiCAN firmware quirks that cost us days

Observed on firmware v4.21; check whether newer releases fixed them.

1. **Config values must be JSON strings.** The firmware calls
   `atoi(item->valuestring)` on everything; a raw numeric value in a
   hand-crafted `/store_config` POST crashes the parser and boot-loops the
   device before Wi-Fi starts. Only configure through the web UI. Recovery
   from the boot-loop is possible via USB re-flash (esptool).
2. **AutoPID byte indexing includes the ISO-TP PCI bytes.** For a multi-frame
   response the buffer is the raw frame payloads concatenated
   (`10 3B 62 A8 70 … | 21 … | 22 …`), so expression indices must account
   for the `2x` consecutive-frame markers. That is why SOC payload bytes
   47–48 end up at `[B59:B60]`.
3. **Single-byte expressions need range syntax.** `[B14]` fails silently
   (nothing is published); use `[B14:B14]` or bare `B14`.
4. **The trailing digit of the PID field is the expected frame count**
   (`22A8709` = `22 A870`, expect 9 frames).
5. **PID list changes require a reboot**, not just Store/Submit.
6. **Reboots mid-poll can publish garbage** (0xFFFF → odometer 6553.5 km,
   SOC spikes). Filter downstream (see the HA package).
