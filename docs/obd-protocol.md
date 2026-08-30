# Honda WN7 — OBD/UDS protocol notes

Reverse-engineered on a 2026 Honda WN7 (electric motorcycle, EU market) using a
MeatPi WiCAN on the diagnostic connector. Ground truth comes from two sources:
calibration against the TFT display over several weeks, and — since 2026-08 — a
**passive bus capture of Honda's official MCS diagnostic tool** alongside its
18-page all-systems report, which let us match report values to raw UDS bytes.
Everything below was observed on one bike — expect variations between markets
and model years, and verify against your TFT display before trusting any value.

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

| Address | Unit | Interesting DIDs |
|---|---|---|
| `0xD4` | BMU (battery management) | `A870` = live status block; `A820`–`A82A`, `DA5x` = counters; `DA10` = battery serial number |
| `0xDE` | Meter / instrument cluster | `F012` = odometer; **`CFA1`/`CFA2` = aggregate/display blocks** (displayed SOC, pack V, temperatures); `F802` = VIN (ASCII — PII, be careful with logs) |
| `0xD0` | OBC (on-board charger) | `CF01`–`CF04` = charge/DCDC block; `CF03` byte 8 = OBC temperature |
| `0xCB` | PCU / DCDC | **`DB00` = charge-connect block** (plug flag, charge-active flag, proximity pilot, 14.7 V DCDC output, temperatures); `E700` |
| `0x60` | Body/ABS (?) | `7122`, `7128`, `712A` (not decoded) |

## Byte indexing: UDS payload position → WiCAN buffer index

WiCAN's AutoPID buffer contains the raw ISO-TP frame payloads *including* the
PCI bytes, so a pure UDS data-byte position `p` (0-based, counted after the
`62 xx xx` header) maps to a WiCAN `B` index like this:

```
p = 0,1,2          →  B5, B6, B7
p ≥ 3:  k = (p-3)//7 + 1,  pos = (p-3)%7   →   B = 8k + 1 + pos
```

This reproduces all verified expressions (e.g. A870 p47:48 → `[B59:B60]`,
F012 p3:4 → `[B9:B10]`). ⚠️ A `[Bx:By]` range expression must **not** span a
frame boundary (PCI byte) — split it into two ranges if it does (see the
odometer expression).

## Useful DIDs (service 0x22)

### `0xD4` (BMU) — DID `A870`: battery status block

56-byte payload, the single most useful DID on the bike. Verified positions
(matched against the official diagnostic report):

| Value | payload pos | WiCAN expression | Notes |
|---|---|---|---|
| **In-Fact SOC %** | p41:42 | `[B52:B53]*0.01` | the BMS's own SOC — best SOC source |
| SOC displayed ×100 | p43:44 | `[B54:B55]*0.01` | tracks the TFT value |
| SOC control % | p45:46 | `[B57:B58]*0.01` | |
| Remaining-energy field | p47:48 | `[B59:B60]` | see legacy SOC formula below |
| **Pack voltage V** | p12:13 | `[B19:B20]*0.1` | ~392 V nominal |
| **Pack current A** | p14:15 | `((S21*256)+B22)*0.1` | **signed**; negative = charging |
| **Cell temp max °C** | p37 | `B47-40` | |
| Cell temp min °C | p38 | `B49-40` | |
| **SOH %** | p49 | `B61` | 100 on a new bike |
| SOCP / SOCE % | p50 / p51 | `B62` / `B63` | 99 / 100 observed; charge-limit candidates |

**Legacy SOC formula** (used before the direct SOC fields were found):
`SOC % = [B59:B60] × 0.11266 + 2.457`. The remaining-energy field is a BMS
*estimate*: the linear fit is good at 15–32 % and near 100 %, but the midrange
drifts (observed up to ~15 % too high around 80 % real SOC — a piecewise
correction was needed). Prefer the direct SOC fields above.

### `0xDE` (meter) — DID `F012`: odometer

Response `62 F0 12 <u32>`; 32-bit value in 0.1 km. Matches the display exactly.
Expression `[B6:B7]*6553.6+[B9:B10]*0.1` (split at the frame boundary).

### `0xDE` — DIDs `CFA1` / `CFA2`: aggregate/display blocks

The cluster's own copies of what it renders:

| Value | DID | payload pos | WiCAN expression |
|---|---|---|---|
| **Displayed SOC %** (integer, exactly the TFT number) | `CFA2` | p30 | `B39` |
| Ambient temperature °C (no offset) | `CFA2` | p18 | `B26` |
| Cell voltage max (÷5 = mV) | `CFA2` | p31:32 | `[B41:B42]/5` |
| Cell voltage min (÷5 = mV) | `CFA2` | p33:34 | `[B43:B44]/5` |
| Pack voltage (copy) | `CFA2` | p24:25 | |
| Plug-state mirror (4→0 when cable in) | `CFA2` | p16 | `B23` |
| **Charge-port temperature °C** (−40) | `CFA1` | p18 | `B26-40` |

WiCAN PIDs: `22CFA29` / `22CFA19` with `ATSHDADEF1;`.

### `0xCB` (PCU) — DID `DB00`: charge-connect block

56-byte block (`22DB009`, `ATSHDACBF1;`). Decoded via before/after snapshots of
plugging the AC cable in:

- **`B15` (p9): `1` = no cable, `3` = cable plugged in** — a clean connect
  flag. It stays at `3` during an active charge; there is no separate
  "charging" code in this byte.
- **`B14` (p8): `1` = not charging, `2` = charging** — the actual charge-active
  flag, verified during a real AC session (2026-08). Together the two bytes
  give the full state: `B15=1` unplugged · `B15=3, B14=1` plugged and idle ·
  `B15=3, B14=2` charging.
- **`[B36:B37]` (p27:28): proximity-pilot resistance** — `0xFFFF` with no
  plug, a finite value (~220) with the cable in.
- p19:20 and p25:26 go `0 → non-zero` with the cable (control-pilot values);
  `B41` (p31) carries the 14.7 V DCDC output.

### Other

- `0xD4` `A820`–`A82A`, `DA5C`, `DA5F`: event/error counter blocks (present,
  not decoded).
- `0xDE` `D300`–`D30A`: per-cell-unit SOH blocks, pattern `00 00 64 xx xx`
  = SOH 100 % plus a capacity value (695 / 631 observed on a new bike).
- `0xD0` `CF03`: payload byte 8 (`[B14:B14]`) is the **OBC temperature**
  (−40 offset) — *confirmed* against the diagnostic report. It is NOT a
  charging flag (an early hypothesis, definitively disproven).

## What the official diagnostic tool does (captured 2026-08)

Honda's MCS tester was captured passively while it produced a full report:

- It reads with plain **service `0x22`** like we do, plus
  `10 01` (DiagnosticSessionControl, *default* session) and periodic
  `3E` (TesterPresent).
- **No `27` SecurityAccess at all** — none of the data above is locked.
- Pack observed: ~392 V, ~96 cells at ~4083 mV, SOH 100 %.

Some DIDs return 0/defaults to our bare `22` polls; the hypothesis that an
actively-held session (`10 01` + `3E`) makes ECUs populate them is untested.

## Open questions

- **Charge limit (max SOC):** the TFT lets you set one; no explicit field
  found yet. Candidates: `A870` SOCE `B63` and the target DC charging voltage
  (~403 V). A full before/after snapshot around a limited session (stopped at
  ~90 % displayed) showed no register carrying the limit — and the bus plus
  12 V die essentially *with* the end of charging (UDS dead < 20 s after the
  last measurement), so the end-of-charge snapshot came back empty. Practical
  workaround: infer the limit in Home Assistant from "charging ended below
  100 %" rather than from a register.
- **Charge-session extras in `DB00`:** p17/p18 go `0 → 1/120` while charging
  (control-pilot duty / AC current limit?), p23:24 carry further CP values.
  Not decoded.

## Negative results (save yourself the time)

- **Trip meters A/B are not readable.** 49 DIDs across all ECUs were dumped
  while the display showed known trip values — no match. Trips are rendered
  only inside the cluster. Workaround: a `utility_meter` helper on the
  odometer sensor.
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
2. **AutoPID byte indexing includes the ISO-TP PCI bytes.** See the
   position-mapping formula above.
3. **Single-byte expressions need range syntax or the bare form.** `[B14]`
   fails silently (nothing is published); use `[B14:B14]` or bare `B14`.
4. **The trailing digit of the PID field is the expected frame count**
   (`22A8709` = `22 A870`, expect 9 frames).
5. **PID list changes require a reboot**, not just Store/Submit.
6. **Reboots mid-poll can publish garbage** (0xFFFF → odometer 6553.5 km,
   SOC spikes). Filter downstream (see the HA package).
7. **Power the WiCAN so it survives ignition-on.** The WN7 diagnostic feed is
   switched; wired in front of the diagnostic connector the WiCAN rides
   through ignition-ON without a reboot (only ignition-OFF kills it). A USB
   powerbank is *not* a good bench supply — most switch off at the WiCAN's
   low draw.
