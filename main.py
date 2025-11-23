import time
import subprocess
import re

from json_memory import (
    load_memory,
    save_memory,
    update_memory,
    annotate_devices_with_new_flag,
    find_offline_devices,
    lookup_vendor,
)

# NEW: import classification helpers
from extras import (
    normalize_mac,
    is_random_mac,
    classify_device,
    detect_zone,
)


def run(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        return ""


# ==========================
#       1. LOAD PING DATA
# ==========================

ping_ips = set()
try:
    with open("alive_ping.txt") as f:
        for line in f:
            ip = line.strip()
            if ip:
                ping_ips.add(ip)
except FileNotFoundError:
    pass


# ==========================
#        2. PARSE ARP
# ==========================

arp_raw = run("ip neigh")
arp_entries = {}  # ip → { ip, mac, state }

if arp_raw:
    for line in arp_raw.splitlines():
        line = line.strip()
        if not line:
            continue

        # IPv4 only
        m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", line)
        if not m:
            continue

        ip = m.group(1)
        if "FAILED" in line:
            continue

        parts = line.split()
        mac = None

        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                mac = normalize_mac(parts[idx + 1])

        if mac is None or mac == "unknown":
            continue

        state = parts[-1].upper() if parts else "UNKNOWN"

        arp_entries[ip] = {"ip": ip, "mac": mac, "state": state}


# ==========================
#      3. MERGE DEVICES
# ==========================

devices = {}

# PING-only
for ip in ping_ips:
    devices[ip] = {
        "ip": ip,
        "sources": {"PING"},
        "mac": None,
        "arp_state": None,
    }

# Merge ARP
for ip, info in arp_entries.items():
    if ip in devices:
        devices[ip]["sources"].add("ARP")
        devices[ip]["mac"] = info["mac"]
        devices[ip]["arp_state"] = info["state"]
    else:
        devices[ip] = {
            "ip": ip,
            "sources": {"ARP"},
            "mac": info["mac"],
            "arp_state": info["state"],
        }


# MEMORY
memory = load_memory()
memory, new_macs = update_memory(memory, devices)
save_memory(memory)
devices = annotate_devices_with_new_flag(devices, new_macs)
offline_devices = find_offline_devices(memory, devices)


# ==========================
#   4. GATEWAY / YOUR IP
# ==========================

gw_ip = "unknown"
gw_mac = "unknown"
gw_vendor = "unknown vendor"

gw_line = run("ip route | grep default | head -n1")
if gw_line:
    parts = gw_line.split()
    if "via" in parts:
        gw_ip = parts[parts.index("via") + 1]
    else:
        gw_ip = parts[2]

# gateway MAC
if gw_ip != "unknown":
    neigh = run(f"ip neigh | grep '^{gw_ip} ' | head -n1")
    if neigh:
        parts = neigh.split()
        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                gw_mac = normalize_mac(parts[idx + 1])
                gw_vendor = lookup_vendor(gw_mac)


# MY IP
my_ip = ""
out = run("ip route get 1.1.1.1 2>/dev/null")
m = re.search(r"\bsrc\s+(\d{1,3}(?:\.\d{1,3}){3})\b", out)
if m:
    my_ip = m.group(1)

my_subnet = ".".join(my_ip.split(".")[:3]) if my_ip else "unknown"


# ==========================
#     5. WIFI DETECTION
# ==========================

ssid = ""
bssid = ""

iw_out = run("iw dev 2>/dev/null")
wifi_iface = None

if iw_out:
    m = re.search(r"Interface\s+(\S+)", iw_out)
    if m:
        wifi_iface = m.group(1)

if wifi_iface:
    iw_link = run(f"iw dev {wifi_iface} link")
    for line in iw_link.splitlines():
        line = line.strip()
        if line.startswith("SSID:"):
            ssid = line.split("SSID:")[1].strip()
        elif line.startswith("Connected to"):
            bssid = normalize_mac(line.split()[2])


# ==========================
#   6. SUBNET GROUPING
# ==========================

groups = {}
for ip, dev in devices.items():
    parts = ip.split(".")
    if len(parts) != 4:
        continue

    subnet = ".".join(parts[:3])
    groups.setdefault(subnet, []).append(dev)


# latency test
def ping_latency(ip: str):
    out = run(f"ping -c1 -W1 {ip}")
    if not out:
        return None
    m = re.search(r"time=(\d+\.\d+)", out)
    return float(m.group(1)) if m else None


# ==========================
#         7. HEADER
# ==========================

print("\n[ YOU ]")
print(f" ├── Your IP: {my_ip or 'unknown'}")
print(f" ├── Your Subnet: {my_subnet}.x")
print(f" ├── Connected SSID: {ssid or 'unknown'}")
print(f" ├── Access Point (BSSID): {bssid or 'unknown'}")
print(f" └── Gateway: {gw_ip}  (MAC: {gw_mac}, Vendor: {gw_vendor})\n")


# ==========================
#     8. PRINT TREE
# ==========================

for subnet, dev_list in groups.items():
    count = len(dev_list)
    percent = round((count / 256) * 100, 2)
    zone = detect_zone(dev_list)

    tag = {
        count < 3: "  (Sparse)",
        count > 80: "  (Heavy)",
    }.get(True, "")

    subnet_mark = "  <== YOUR SUBNET" if subnet == my_subnet else ""

    print(
        f"     ├── {subnet}.x  ({count} hosts, {percent}% used) [{zone}]{tag}{subnet_mark}"
    )

    # latency sample
    sample = next(
        (d["ip"] for d in dev_list if "PING" in d["sources"]), dev_list[0]["ip"]
    )
    latency = ping_latency(sample)
    if latency is not None:
        print(f"     │    Avg latency (sample {sample}): {latency} ms")

    # sort devices
    dev_list_sorted = sorted(dev_list, key=lambda d: int(d["ip"].split(".")[3]))

    for dev in dev_list_sorted:
        ip = dev["ip"]
        mac = normalize_mac(dev["mac"] or "unknown")
        vendor = memory.get(mac, {}).get("vendor", "unknown vendor")

        random_flag = is_random_mac(mac)
        device_type = classify_device(mac, vendor, random_flag)

        srcs = dev["sources"]
        if srcs == {"PING"}:
            src_label = "PING"
        elif srcs == {"ARP"}:
            src_label = "ARP"
        else:
            src_label = "PING+ARP"

        you = "  (YOU)" if ip == my_ip else ""
        new_tag = "  (NEW)" if dev.get("is_new") else ""
        rand = " (Random)" if random_flag else ""

        print(
            f"     │\n"
            f"     │  └── {ip} [src={src_label}, mac={mac}, vendor={vendor}, type={device_type}{rand}]{you}{new_tag}"
        )


# ==========================
#         9. SUMMARY
# ==========================

total_hosts = len(devices)
total_subnets = len(groups)

print("\n----------------------------")
print(" Network Summary")
print("----------------------------")
print(f" Total unique hosts (hybrid): {total_hosts}")
print(f" Total subnets active:        {total_subnets}")
print("----------------------------\n")

if offline_devices:
    print(" Offline devices:")
    for entry in offline_devices:
        last_ip = entry.get("last_ip", "unknown")
        vendor = entry.get("vendor", "unknown vendor")
        mac = entry.get("mac", "unknown")
        last_seen = entry.get("last_seen", 0)
        age_min = int((time.time() - last_seen) / 60)

        print(
            f"  |\n"
            f"  └── {last_ip}  [MAC={mac}, vendor={vendor}, offline {age_min} min ago]"
        )
    print("----------------------------\n")
else:
    print(" No offline devices.")
    print("----------------------------\n")
