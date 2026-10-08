# Somfy Huna blinds for Home Assistant

Local Bluetooth control of **Somfy Huna** motorised roller blinds: the ones
that show up over Bluetooth as `MyHunaBlind` and are normally driven by the
Hunablinds app or the Huna wall switch. No hub, no cloud, no pairing.

> **Unofficial and experimental.** Not affiliated with or endorsed by Somfy.
> Tested on two blinds (hardware `5141722A001`, software `2.4.2`).
> Use at your own risk.

## What you get

For each blind:

| Entity | What it does |
|---|---|
| **Cover** | Open, close, stop and set position, with opening / closing states |
| Battery level | Critical / low / medium / high |
| Battery | Exact percentage, refreshed each time a command is sent |

Position, battery level and availability are read from the short Bluetooth
broadcast the blind sends out anyway. Home Assistant only **connects** to a
blind when you move it, so the integration does not drain the blind's battery
while idle. Moves made from the wall switch or the app show up in Home
Assistant the same way.

The app's timers, sunrise / sunset routines and end-limit setup are left
alone. Use Home Assistant automations for scheduling.

## Before you start

You need:

1. **Home Assistant** with [HACS](https://hacs.xyz) installed. Developed and
   tested on 2026.9; it should work on 2024.11 or newer.
2. **Bluetooth within a few metres of the blinds.** Either a Bluetooth adapter
   on the Home Assistant machine, or an
   [ESPHome Bluetooth proxy](https://esphome.github.io/bluetooth-proxies/)
   (a generic ESP32 board is enough) placed near the blinds. Both have been
   tested.

Nothing needs doing on the blinds themselves, and they keep working from the
Huna app and wall switch.

## Install

### With HACS (recommended)

1. In Home Assistant open **HACS**.
2. Open the three-dot menu (top right) and choose **Custom repositories**.
3. Paste `https://github.com/haaaarps/hass-somfy-huna`, choose type
   **Integration**, and select **Add**.
4. Find **Somfy Huna Blinds** in HACS and select **Download**.
5. **Restart Home Assistant.**

### By hand

Copy the `custom_components/somfy_huna` folder from this repository into the
`custom_components` folder of your Home Assistant configuration, then restart
Home Assistant.

## Set up

After the restart, each blind in range should appear under
**Settings → Devices & services** as a discovered device. Select **Add**, give
it a name, and you are done.

If nothing is discovered: **Add integration → Somfy Huna Blinds** and pick a
blind from the list.

### If open and close are the wrong way round

Open the blind's **Configure** dialog and turn on **Swap open and closed**.

### Moving several blinds as one

Create a [cover group](https://www.home-assistant.io/integrations/group/#cover-groups)
helper containing the blinds. The group then works from dashboards, voice
assistants and automations as a single cover.

## Add it to a dashboard

```yaml
type: tile
entity: cover.my_blind
features:
  - type: cover-open-close
  - type: cover-position
```

## Things to know

- **The first press takes a second or two**, because Home Assistant has to
  connect. The connection is then kept for 20 seconds, so a stop or a second
  move straight afterwards is instant.
- **Ignored presses are retried.** If a blind has not started moving six
  seconds after a command, the move is sent again, up to twice.
- **While Home Assistant is connected** (those 20 seconds), the app or wall
  switch may not reach that blind.
- **Bluetooth only reaches a few metres through walls.** If a blind shows as
  unavailable, move the adapter or proxy closer.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Blind not discovered | Out of Bluetooth range, or the Huna app is connected to it |
| "…not in range of a connectable Bluetooth adapter or proxy" | The adapter that hears the blind cannot make connections. Use a connectable adapter or an ESPHome proxy with active connections |
| Blind opens when you press close | Turn on **Swap open and closed** for that blind |
| Battery percentage is "unknown" | It is only read when a command is sent. Move the blind once |

## How it works

The protocol was worked out from the Hunablinds Android app for the purpose of
interoperability. Somfy does not document it.

**Broadcast** (manufacturer ID `1480`), seven bytes:

| Bytes | Meaning |
|---|---|
| 0–1 | firmware ID |
| 2–4 | last three bytes of the blind's address |
| 5 | position, 0–255 |
| 6 | status: bits 0–1 battery level (0 critical … 3 high), bit 7 set while the motor runs |

**Authentication**, once per connection: read System ID (`2a23`) and the
challenge characteristic, then write back `00` followed by the first 16 bytes
of AES-128-CBC(challenge), using the same key as the app. The IV is derived
from the System ID and the challenge.

**Commands:**

| Characteristic | Value | Effect |
|---|---|---|
| position | big-endian `u16`, 0–51200 | move to that position (0 = one end limit, 51200 = the other) |
| adjust | `01` | stop |

Open and close are sent as position moves to the two ends. The adjust
characteristic also accepts `02` (top) and `03` (bottom), but in testing a
"top" command stopped as soon as the connection closed, so they are not used.

Adjust values `04` and `05` **re-program the blind's end limits**. This
integration never sends them, and you should not either.

## Licence

MIT. See [LICENSE](LICENSE).
