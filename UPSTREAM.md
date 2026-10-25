# Upstream

- PR: https://github.com/magmu/tuya-ble-mesh/pull/23
- Comment: https://github.com/11z4t/tuya-ble-mesh/issues/2#issuecomment-6404745270

The text as posted:

## PR to magmu/tuya-ble-mesh

**Title:** Tuya 0x0102 lights: E2 brightness/white/RGB, no flash on reconnect

The patch in `patches/` as a PR from a fork of magmu/tuya-ble-mesh.

> Adds brightness, white and RGB for Tuya `0x0102` lights using the `0xE2` packet the Smart Life app sends (`09 | R G B | warm cold | brightness % | 00 | mask`, vendor `0x0102`), as captured in 11z4t#2. Tested on two GE imagine Paragon RGB+CCT downlights (Tuya `9lcrglpq`, status vendor `05 01`), which ignore compact DP writes.
>
> Also stops these lights flashing on every connect: a light on its own mesh credentials is logged in to without re-sending `SET_NAME`/`SET_PASS`. That needs the packet sequence to start above the previous run (the light drops lower sequence numbers), so it now starts from the clock. Lights on `out_of_mesh` are provisioned as before.
>
> Unit suite: 2105 passed. `test_brightness_and_temp_use_compact_dps` is replaced by `E2` tests, since it asserted the compact-DP path this changes. I couldn't test on a WC bulb (pid bXun1QKL), but its capture in #2 shows the same `E2` packets from the app.
>
> Full write-up: https://github.com/oscarmorrison/ge-imagine-tuya-ble-mesh

## Comment on 11z4t/tuya-ble-mesh#2

> Thanks for the capture. Your `0xE2` brightness/white payloads were the missing piece for GE imagine Paragon RGB+CCT downlights (Tuya `9lcrglpq`, Australia). Same packet, plus RGB: `09 | R G B | warm cold | brightness % | 00 | mask`, with mask `04` brightness, `18` white, `1C` white + brightness, `E0` RGB. Write-up and a patch for the magmu fork: https://github.com/oscarmorrison/ge-imagine-tuya-ble-mesh
