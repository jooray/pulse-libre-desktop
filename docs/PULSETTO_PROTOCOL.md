# Pulsetto BLE Protocol

This document describes the Bluetooth Low Energy protocol used by Pulsetto
devices.

The BLE behavior is the same for both **Pulsetto Lite** and **Pulsetto Fit**.
Commands, startup sequence, stop sequence, battery parsing, and side selection
work the same way on both models.

## Key Points

- Pulsetto Lite and Pulsetto Fit use the same BLE protocol.
- The standard Pulsetto session types do not select different waveforms over
  BLE.
- For the standard programs, the practical difference is the recommended
  session length.
- The Sleep program starts with the LED dimmed (`E`).
- There is no need for a program picker in third-party clients that only need
  basic stimulation control.

## BLE Service and Characteristics

Pulsetto uses the Nordic UART Service over GATT.

| Role | UUID | Description |
|------|------|-------------|
| Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | Nordic UART Service |
| RX (write) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | App to device |
| TX (notify) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | Device to app |

Commands are ASCII strings terminated by `\n`.

## Write Modes

Two write modes are used:

| Write Mode | Commands |
|------------|----------|
| `writeWithResponse` | `+`, `-` |
| `writeWithoutResponse` | everything else |

Use `writeWithResponse` for ramp and stop transitions, and
`writeWithoutResponse` for normal control and status commands.

## Discovery and Identification

Devices advertise with a BLE name starting with `Pulsetto`.

After connecting, the client can query:

| Command | Meaning | Example response |
|---------|---------|------------------|
| `v\n` | firmware version | `fw:1.1.22` |
| `i\n` | device identity | `Pulsetto_ST_02` |

The identity string is informational. It is not needed to choose a different
BLE command set.

## Command Reference

| ASCII | Meaning |
|-------|---------|
| `+` | ramp up |
| `-` | ramp down / stop |
| `U` | update session |
| `A` | stimulate left side |
| `C` | stimulate right side |
| `D` | stimulate both sides |
| `Q` | query battery voltage |
| `0` | set intensity 0 |
| `1`-`9` | set intensity 1 through 9 |
| `u` | query charging status |
| `v` | query firmware version |
| `i` | query device identity |
| `E` | low LED level |
| `F` | medium LED level |
| `G` | high LED level |

## LED Commands

`E`, `F`, and `G` are LED level commands.

They do not select different stimulation programs or different BLE-level wave
patterns.

Default behavior:

- Sleep starts with `E`.
- Other standard programs typically start with `F`.
- A client can choose a fixed LED setting if desired.

## Session Start Sequence

The session start sequence is the same on Lite and Fit.

1. Send `+\n` using `writeWithResponse`
2. Send `-\n` using `writeWithResponse`
3. Wait 250 ms
4. Send `0\n`
5. Wait 450 ms
6. Send `5\n`
7. Wait 450 ms
8. Send `0\n`
9. Wait 450 ms
10. Send target intensity `1\n` to `9\n`
11. Wait 250 ms
12. Send side command, usually `D\n`
13. Send LED command, usually `E\n` or `F\n`

The `0 -> 5 -> 0 -> target` pattern is part of the normal startup sequence.

## Session Stop Sequence

1. Send `+\n` using `writeWithResponse`
2. Send `-\n` using `writeWithResponse`
3. Send `-\n` using `writeWithResponse`

## Changing Intensity During a Session

To change intensity while stimulation is active, send `1\n` through `9\n`
directly.

To pause output without fully ending the session, send `0\n`.

## Side Selection

| Command | Side |
|---------|------|
| `D\n` | both |
| `A\n` | left |
| `C\n` | right |

`D\n` is the normal default.

## Status Polling

During a session, poll every 3 seconds:

1. Send `u\n`
2. Send `Q\n`

When idle, a slower polling interval is sufficient.

On connect, it is useful to query:

1. `v\n`
2. `i\n`

## Responses

### Battery

Battery notifications use a `Batt:` prefix, for example:

```text
Batt:3.97
```

Battery percentage:

```text
percentage = round((voltage - 3.5) / 0.4 * 100)
```

Effective range:

- `3.5 V` = `0%`
- `3.9 V` = `100%`

Additional status notifications can include:

```text
mode:0
BR:100
Batt:3.97
```

### Charging

Charging responses are binary:

| Response | Meaning |
|----------|---------|
| `u\x011` | charging |
| `u\x010` | not charging |

### Firmware

Firmware responses begin with `fw:`:

```text
fw:1.1.22
```

## Programs

### Standard Programs

For the standard Pulsetto programs, there is no separate BLE command that picks
Stress, Anxiety, Sleep, Burnout, Pain, or similar modes.

From the device control point of view, these programs are the same kind of BLE
session. The practical difference is the recommended duration.

Typical defaults:

| Program | Default duration |
|---------|------------------|
| Stress | 4 min |
| Anxiety | 6 min |
| Sleep | 10 min |
| Burnout | 6 min |
| Pain | 20 min |
| Head Pain | 6 min |
| Inflammation | 4 min |
| Gut Health | 5 min |
| Personal | 8 min |

This is why a simple client with just time and intensity controls is enough for
normal Pulsetto use.

### Guided Meditation Programs

Some guided meditation sessions add software-level timing intervals that turn
stimulation on and off at specific times. These intervals are orchestration in
the client layer, not a different BLE waveform mode.

Without the guided audio flow, these interval patterns are usually not useful.

## Practical Implementation Guidance

For a clean third-party client:

- use one BLE code path for Lite and Fit
- use the full start sequence every time
- use the full stop sequence every time
- use `D` for both sides unless the user chooses otherwise
- use `E` if you want the least distracting LED behavior
- expose time and intensity as the primary controls

