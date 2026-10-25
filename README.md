# GE imagine downlights in Home Assistant, fully local over Bluetooth

How to control **GE imagine Paragon RGB+CCT downlights** (G13239L, sold in Australia) from Home Assistant with no cloud or gateway. They're Tuya Telink Bluetooth mesh lights that usually live in the Smart Life app. On/off, brightness, warm/cool white and colour all work from HA, and the lights don't flash when the wall switch turns them on.

This builds on [magmu/tuya-ble-mesh](https://github.com/magmu/tuya-ble-mesh), a fork of [11z4t/tuya-ble-mesh](https://github.com/11z4t/tuya-ble-mesh). The key brightness bytes came from an HCI capture in [11z4t/tuya-ble-mesh#2](https://github.com/11z4t/tuya-ble-mesh/issues/2).

- [`patches/magmu-tuya-ble-mesh-v0.42.13.patch`](patches/magmu-tuya-ble-mesh-v0.42.13.patch): the changes to the integration, with tests (the unit suite passes). Apply it with `git am` on top of magmu v0.42.13. It's also open as [magmu/tuya-ble-mesh#23](https://github.com/magmu/tuya-ble-mesh/pull/23).
- [`tools/`](tools): the scripts used to work the protocol out.

## The lights

| | |
| --- | --- |
| Product | GE imagine Paragon RGB+CCT downlight, G13239L |
| Inside | Tuya Telink proprietary BLE mesh (not SIG Mesh). Tuya product `9lcrglpq`, category `dj` |
| Advertises as | `out_of_mesh` after a reset (MAC prefix `DC:23:4D`) |
| Cloud data points | 1 `switch_led`, 3 `bright_value_v2`, 4 `temp_value_v2` (none of these work locally as compact DPs) |
| Status vendor bytes | `05 01` |

## The protocol

Commands go to characteristic `…1912` as normal Telink packets: `[dest LE16][opcode][vendor 2 B][params]`, encrypted with the session key. The destination doesn't matter (`0x0000`, the light's own address and `0xFFFF` all work).

The light only obeys vendor bytes with `01` as the second byte (`02 01` and `05 01` work; `01 10`, `11 02` and `00 00` are ignored). Use `02 01`.

| What | Opcode | Params |
| --- | --- | --- |
| On / off | `D0` | `01 00 00` / `00 00 00` |
| Brightness, white, colour | `E2` | `09 · R G B · warm cold · brightness % · 00 · mask` |
| Status query | `DA` | `10`. The light answers with `DB` |

The `E2` mask says which fields to apply:

| Mask | Applies | Example |
| --- | --- | --- |
| `04` | brightness 1–100 % | `09 00 00 00 00 00 14 00 04` = 20 % |
| `18` | white (warm + cold = 255) | `09 00 00 00 FF 00 00 00 18` = full warm |
| `1C` | white + brightness | `09 00 00 00 7F 80 64 00 1C` = neutral, 100 % |
| `E0` | RGB, switches to colour mode | `09 FF 00 00 00 00 00 00 E0` = red |

- White commands (`18`/`1C`) switch the light back to white mode.
- In colour mode, the `04` brightness command scales the RGB values.
- `20`, `40` and `80` on their own do nothing.

Replies, decrypted (after the 7-byte header):

- **`DB` status:** `db 05 01 | R G B | w1 w2 | brightness % | 00 | mode`. `mode` is the last mask (`1c` white, `e0` colour). On these lights `w1` follows the warm byte of the command. The WC bulb in #2 reports cold first, so check this on your own light.
- **`DC`:** sent after every change: `<addr> <seq> <brightness %> <ff white | aa colour>`.

Other things seen, in case they help someone:

- `CF` makes the light send its Tuya identity in eight `DF` chunks. These may include its auth key, so don't post them.
- `D4`, `E1`, `E7` and `EA` (answered with `EB`) echo their parameter.
- Compact DP writes (`D2`, DP 2/3/122/123/124, values 50 and 500, any vendor) are ignored, as is every single-byte `D1`–`FF` command.

## No flash when the wall switch turns them on

Both lights are on one wall switch, so they boot and reconnect several times a day. The light doesn't flash when it boots, but it flashed every time HA connected.

- **Cause:** on every connect the integration re-sent the mesh name and password (`SET_NAME`/`SET_PASS`, PLAT-733), and the light blinks for that.
- **Logging in without the rewrite isn't enough while the light uses the defaults.** The light then answers status queries but ignores commands. The reason is that the light remembers the last packet sequence number it saw and drops anything lower, and HA restarts counting from 0. The rewrite resets that counter, which is why it always seemed necessary.
- **Fix, in the patch:**
  1. Give each light its own mesh name and password once (`tools/mesh_creds.py set`). Use a different name per light so their meshes stay separate.
  2. When a light isn't on `out_of_mesh`, log in only, with no rewrite.
  3. Start the sequence counter from the clock (`int(time.time())`, 24-bit), so it's always above the last run. It wraps about every 194 days.

## Setting up a light

1. In Smart Life, remove the light with **Disconnect and wipe data**. It comes back as `out_of_mesh`.
2. Install magmu/tuya-ble-mesh v0.42.13 with the patch applied.
3. Give the light its own credentials with `tools/mesh_creds.py` (see the instructions at the top of the file).
4. Add it in HA: device type **LED Light**, the new mesh name and password, vendor `0x0102`.

## How it was worked out

- **BlueZ drops the notifications.** These lights have no real notification descriptor, so `start_notify` times out ([bluez#2383](https://github.com/bluez/bluez/issues/2383)), and HA never hears the light's replies. They still reach the radio, though: `hcidump -i hci0 -X -t` on the HAOS host shows them.
- **Blind testing:** `tools/raw_command_service.py` adds a developer-only HA service that sends exact bytes and logs the session key. `tools/mesh_probe.py` sends a list of commands, follows each with a `DA 10` status query, and decrypts the light's replies from `hcidump`. That gave a yes/no answer for each candidate without anyone watching the light.
- **Gotchas:**
  - The first connection after an HA start drops about 20 seconds later; the reconnect is stable.
  - Reloading the integration doesn't re-import the library, so restart HA after editing it.
  - Removing a light from Smart Life wipes it.
