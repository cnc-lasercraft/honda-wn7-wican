# Honda RoadSync BLE — protocol notes

Findings from a static analysis of the Honda RoadSync Android app
(`com.honda.ms.dm.sab`, v26.2.11, developed by Drivemode), done while looking
for a battery-data channel. **Bottom line: RoadSync is not a telemetry
channel — the interesting data stays on the CAN bus.**

## Architecture

The app speaks a proprietary BLE protocol called **SAB** ("Smart Application
for Bikes", `com.drivemode.sab.ble.*`):

1. BLE scan → find motorcycle by advertisement
2. Security handshake (custom crypto, `SecurityController`/`Crypto`)
3. Vehicle identification (VehicleInformationService characteristics)
4. Assignment (register phone with motorcycle)
5. Data communication (navigation, music, calls, screen projection)

## GATT services

| Service | UUID |
|---|---|
| VehicleInformationService | `4d87b1ea-528b-4798-b002-e2e1442a2e86` |
| SecurityService | `592c1017-9c7b-4a35-aba6-f268592fb8fc` |
| AssignmentService | `f0746e98-61d6-4570-be7e-7635c65c21cb` |
| DataCommunicationService | `8536e103-6771-4d4b-9702-287cb5e1340f` |
| DFUService (firmware update) | `6c060578-d1d9-460a-b86f-eb97f01b2227` |

VehicleInformationService characteristics include VehicleType
(`0x01` = MOTORCYCLE), CategoryId (`0x09` = **HEV** — the app already knows
about electric bikes) and SeriesCode (the WN7 will report a new code).

## Why this is a dead end for telemetry

- **No battery PIDs in the protocol.** The EV menus on the TFT are rendered by
  the bike itself; the app never receives battery data.
- **Screen projection goes the other way** — the app projects navigation/music
  *onto* the display.
- The link is encrypted with a custom handshake; impersonating the app would
  require reversing the crypto for no data gain.

Use the CAN/UDS route ([obd-protocol.md](obd-protocol.md)) instead.
