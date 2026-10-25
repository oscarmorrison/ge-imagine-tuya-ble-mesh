"""Give a Tuya Telink mesh light its own mesh credentials, then test a login-only connect.

Run inside the Home Assistant container (it uses the tuya_ble_mesh library and bleak),
with the light's HA integration disabled so nothing else holds the connection:

  docker exec -i -e MAC=<mac> -e NEW_NAME=<name> -e NEW_PASS=<pass> homeassistant python3 - set < mesh_creds.py
  docker exec -i -e MAC=<mac> -e NEW_NAME=<name> -e NEW_PASS=<pass> homeassistant python3 - test < mesh_creds.py

`set` moves the light from out_of_mesh/123456 to the new credentials (it flashes once).
`test` logs in with them only and dims to 40 % then back to 100 %.
Names and passwords are at most 16 bytes.
"""
import asyncio, os, sys
sys.path.insert(0, "/config/custom_components/tuya_ble_mesh/lib")
from bleak import BleakClient
from tuya_ble_mesh.provisioner import pair, set_mesh_credentials
from tuya_ble_mesh.protocol import encode_command_packet
from tuya_ble_mesh.const import TELINK_CHAR_COMMAND

MAC = os.environ["MAC"]
from tuya_ble_mesh.device import mac_to_bytes
MACB = mac_to_bytes(MAC)
NEW_NAME, NEW_PASS = os.environ["NEW_NAME"].encode(), os.environ["NEW_PASS"].encode()

async def main(mode):
    async with BleakClient(MAC, timeout=30) as c:
        if mode == "set":
            key, _ = await pair(c, b"out_of_mesh", b"123456")
            await set_mesh_credentials(c, key, NEW_NAME, NEW_PASS)
            print("credentials set")
        else:
            key, _ = await pair(c, NEW_NAME, NEW_PASS)
            print("login ok")
            for seq, lvl in ((1, 0x28), (2, 0x64)):
                pkt = encode_command_packet(key, MACB, seq + 5000, 0xFFFF, 0xE2,
                    bytes([9, 0, 0, 0, 0, 0, lvl, 0, 4]), vendor_id=bytes([2, 1]))
                await c.write_gatt_char(TELINK_CHAR_COMMAND, pkt, response=False)
                print("sent bright", lvl)
                await asyncio.sleep(3)

asyncio.run(main(sys.argv[1]))
