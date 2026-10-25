"""Send raw Telink commands to a Tuya Telink mesh light and decode its replies.

Usage: HA_URL=http://<ha>:8123 HOMEASSISTANT_TOKEN=... HA_SSH=<ssh host for the HAOS host> uv run --with cryptography --with bleak --with bleak-retry-connector \
         --with aiohttp --with requests python tools/mesh_probe.py <lib_dir> <tests.json>
tests.json: list of {"label": str, "cmd": {opcode, vendor, params, dest}}. Each test is
followed by a status query; replies are captured with hcidump on the HAOS host.
"""
import json, os, re, subprocess, sys, time
import requests

sys.path.insert(0, sys.argv[1])
from tuya_ble_mesh.protocol import decrypt_notification  # noqa: E402

HA = os.environ.get("HA_URL", "http://homeassistant.local:8123") + "/api/services/tuya_ble_mesh/raw_command"
HDR = {"Authorization": f"Bearer {os.environ['HOMEASSISTANT_TOKEN']}"}
QUERY = {"opcode": "DA", "vendor": "0501", "params": "10", "dest": "FFFF"}
GAP = float(os.environ.get("GAP", "1.6"))


def send(cmd):
    requests.post(HA, headers=HDR, json=cmd, timeout=30).raise_for_status()
    return time.time()


def ssh(cmd):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", os.environ.get("HA_SSH", "ha"), cmd], capture_output=True, text=True).stdout


tests = json.load(open(sys.argv[2]))
send({"opcode": "00", "vendor": "0000", "key": True})
time.sleep(1)
log = ssh("docker logs --since 30s homeassistant 2>&1 | grep 'RAW key' | tail -1")
key = bytes.fromhex(re.search(r"key=([0-9a-f]+)", log).group(1))
mac = bytes.fromhex(re.search(r"mac=([0-9a-f]+)", log).group(1))

dur = int(len(tests) * GAP * 2 + 15)
ssh(f"(timeout {dur} hcidump -i hci0 -X -t > /tmp/probe.txt 2>&1 &)")
time.sleep(2)
marks = []
for t in tests:
    marks.append((t["label"], send(t["cmd"])))
    time.sleep(GAP)
    send(QUERY)
    time.sleep(GAP)
time.sleep(3)
dump = ssh("cat /tmp/probe.txt").splitlines()

# hcidump prints host-local time; convert via the first timestamp's date
notes = []
for i, line in enumerate(dump):
    if "Handle notify" in line:
        ts = dump[i - 1].split(" >")[0]
        val = bytes(int(x, 16) for x in dump[i + 2].split("value")[1].split())
        epoch = time.mktime(time.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")) + float("0." + ts[20:26])
        try:
            dec = decrypt_notification(key, mac, val)
            notes.append((epoch, dec[3:5].hex(), dec[7:].hex(" ")))
        except Exception as exc:  # noqa: BLE001
            notes.append((epoch, "??", f"decrypt failed {exc}"))

# Pi clock is UTC; local epoch from time.mktime assumes local tz, so align on offset of first note
offset = time.timezone - (3600 if time.daylight and time.localtime().tm_isdst else 0)
for idx, (label, t0) in enumerate(marks):
    t1 = marks[idx + 1][1] if idx + 1 < len(marks) else t0 + 3 * GAP + 5
    got = [f"src{s} {p}" for e, s, p in notes if t0 <= e - offset < t1]
    print(f"{label:<34} -> " + (" || ".join(got) if got else "(no reply)"))
