"""Developer-only Home Assistant service: tuya_ble_mesh.raw_command.

Append this to custom_components/tuya_ble_mesh/__init__.py and call
`await _async_register_raw(hass)` right after `await _async_register_services(hass)`.
It sends exact Telink bytes to every configured light and, with `key: true`,
logs the session key so tools/mesh_probe.py can decrypt replies from hcidump.
The session key is per connection, but do not leave this installed.
"""


# --- Local test hook (smart-home repo): send exact bytes to a mesh light ---
async def _async_register_raw(hass: HomeAssistant) -> None:
    import voluptuous as vol

    from tuya_ble_mesh.protocol import encode_command_packet

    if hass.services.has_service(DOMAIN, "raw_command"):
        return

    async def handle_raw(call: ServiceCall) -> None:
        opcode = int(call.data["opcode"], 16)
        params = bytes.fromhex(call.data.get("params", ""))
        vendor = bytes.fromhex(call.data["vendor"])  # wire order, e.g. "0201" = 0x0102
        dest = int(call.data.get("dest", "0000"), 16)
        for entry in hass.config_entries.async_entries(DOMAIN):
            runtime = getattr(entry, "runtime_data", None)
            if runtime is None:
                continue
            dev = runtime.coordinator.device
            if call.data.get("key"):
                _LOGGER.warning("RAW key=%s mac=%s", dev._conn.session_key.hex(), dev._mac_bytes.hex())
                continue
            seq = await dev._conn.next_sequence()
            packet = encode_command_packet(
                dev._conn.session_key, dev._mac_bytes, seq, dest, opcode, params, vendor_id=vendor
            )
            await dev._conn.write_command(packet)
            _LOGGER.warning(
                "RAW op=0x%02X vendor=%s params=%s dest=0x%04X seq=%d",
                opcode, vendor.hex(), params.hex(), dest, seq,
            )
            if call.data.get("read"):
                from tuya_ble_mesh.const import TELINK_CHAR_STATUS
                from tuya_ble_mesh.protocol import decode_status, decrypt_notification

                await asyncio.sleep(float(call.data.get("wait", 0.6)))
                raw = await dev._conn._client.read_gatt_char(TELINK_CHAR_STATUS)
                try:
                    plain = decrypt_notification(dev._conn.session_key, dev._mac_bytes, bytes(raw))
                    _LOGGER.warning("RAW read enc=%s dec=%s status=%s", bytes(raw).hex(), plain.hex(), decode_status(plain))
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning("RAW read enc=%s (decrypt failed: %s)", bytes(raw).hex(), exc)

    hass.services.async_register(
        DOMAIN,
        "raw_command",
        handle_raw,
        schema=vol.Schema(
            {
                vol.Required("opcode"): str,
                vol.Required("vendor"): str,
                vol.Optional("params", default=""): str,
                vol.Optional("dest", default="0000"): str,
                vol.Optional("read", default=False): bool,
                vol.Optional("key", default=False): bool,
                vol.Optional("wait", default=0.6): vol.Coerce(float),
            }
        ),
    )
