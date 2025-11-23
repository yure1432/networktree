import json
import os
import time
import subprocess

MEMORY_FILE = "devices.json"


# helper to run shell commands
def run(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        return ""


# MAC vendor lookup
def lookup_vendor(mac: str) -> str:
    if not mac or mac == "unknown":
        return "unknown vendor"

    try:
        oui = mac[:8].replace(":", "").upper()
        line = run(f"grep -i {oui} /usr/share/hwdata/oui.txt | head -n1")
        return line.strip() if line else "unknown vendor"
    except:
        return "unknown vendor"


# load memory JSON
def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}

    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}


# save memory JSON
def save_memory(memory):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=2)
    except:
        pass


# update memory with new scan results
def update_memory(memory, devices):
    """
    memory: dict keyed by MAC
    devices: dict keyed by IP, each device has:
        - ip
        - mac
        - sources
        - arp_state
    Returns:
        updated_memory, new_macs (set)
    """

    now = time.time()
    new_macs = set()

    for ip, dev in devices.items():
        mac = dev.get("mac")
        if not mac or mac == "unknown":
            continue

        # NEW DEVICE
        if mac not in memory:
            memory[mac] = {
                "mac": mac,
                "first_seen": now,
                "last_seen": now,
                "last_ip": ip,
                "ips_seen": [ip],
                "seen_count": 1,
                "vendor": lookup_vendor(mac),
            }
            new_macs.add(mac)

        # EXISTING DEVICE
        else:
            entry = memory[mac]
            entry["last_seen"] = now
            entry["last_ip"] = ip

            if ip not in entry["ips_seen"]:
                entry["ips_seen"].append(ip)

            entry["seen_count"] = entry.get("seen_count", 0) + 1

            if entry.get("vendor") in (None, "", "unknown vendor"):
                entry["vendor"] = lookup_vendor(mac)

    return memory, new_macs


# attach `(NEW)` flag to device objects
def annotate_devices_with_new_flag(devices, new_macs):
    for dev in devices.values():
        mac = dev.get("mac")
        dev["is_new"] = mac in new_macs if mac else False

    return devices


# return a list of memory entries that were NOT present in this scan.


def find_offline_devices(memory, devices):

    offline = []

    # Current MACs seen
    current_macs = {dev.get("mac") for dev in devices.values() if dev.get("mac")}

    for mac, entry in memory.items():
        if mac not in current_macs:
            offline.append(entry)
