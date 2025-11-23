import time
import subprocess

from json_memory import (
    load_memory,
    save_memory,
    update_memory,
    annotate_devices_with_new_flag,
    find_offline_devices,
)


def run(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        return ""


# 1) Load fping (ICMP) results

ping_ips = set()
try:
    with open("alive_ping.txt") as f:
        for line in f:
            ip = line.strip()
            if ip:
                ping_ips.add(ip)
except FileNotFoundError:
    pass


# 2) Parse ARP table (ip neigh)
arp_raw = run("ip neigh")
arp_entries = {}  # ip → { ip, mac, state }

if arp_raw:
    for line in arp_raw.splitlines():
        parts = line.split()
        if not parts:
            continue

        ip = parts[0]

        # Skip IPv6
        if ":" in ip:
            continue

        # Skip entries like:
        # "FAILED"
        if parts[-1] == "FAILED":
            continue

        # Look for MAC
        mac = None
        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                mac = parts[idx + 1]

        # ARP CHECKS (IMPORTANT)

        # Skip entries with no MAC → hotspot fake ARP
        if mac is None:
            continue

        # Skip placeholder MACs
        if mac.lower() in ["00:00:00:00:00:00", "ff:ff:ff:ff:ff:ff"]:
            continue

        # If passed all filters -> real device
        state = parts[-1]
        arp_entries[ip] = {"ip": ip, "mac": mac, "state": state}


# 3) Merge into device table
devices = {}
# structure:
# devices[ip] = {
#   "ip": ...,
#   "sources": {"PING","ARP"},
#   "mac": ...,
#   "arp_state": ...
# }

# add ping-only entries
for ip in ping_ips:
    devices[ip] = {"ip": ip, "sources": {"PING"}, "mac": None, "arp_state": None}

# merge ARP
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

# Memory integration

memory = load_memory()
memory, new_macs = update_memory(memory, devices)
save_memory(memory)
devices = annotate_devices_with_new_flag(devices, new_macs)
offline_devices = find_offline_devices(memory, devices)


# 4) Gateway / your IP / WiFi info
gw_ip = "unknown"
gw_mac = "unknown"
gw_vendor = "unknown vendor"

# gateway IP
gw_line = run("ip route | grep default | head -n1")
if gw_line:
    try:
        gw_ip = gw_line.split()[2]
    except:
        pass

# gateway MAC + vendor
if gw_ip != "unknown":
    neigh = run(f"ip neigh | grep '^{gw_ip} ' | head -n1")
    if neigh:
        parts = neigh.split()
        if "lladdr" in parts:
            idx = parts.index("lladdr")
            if idx + 1 < len(parts):
                gw_mac = parts[idx + 1]

        # vendor lookup
        try:
            oui = gw_mac[:8].replace(":", "").upper()
            line = run(f"grep -i {oui} /usr/share/hwdata/oui.txt | head -n1")
            if line:
                gw_vendor = line.strip()
        except:
            pass

# Your IP
my_ip = run("ip route get 1.1.1.1 | awk '{print $7}'")
my_subnet = ".".join(my_ip.split(".")[:3]) if my_ip else "unknown"

# WiFi info
ssid = ""
bssid = ""

iw = run("iw dev wlan0 link")
for line in iw.splitlines():
    line = line.strip()
    if line.startswith("SSID:"):
        ssid = line.split("SSID:")[1].strip()
    elif line.startswith("Connected to"):
        parts = line.split()
        if len(parts) >= 3:
            bssid = parts[2]


# 5) Group devices by /24 subnet
groups = {}  # subnet → list of device dicts

for ip, dev in devices.items():
    parts = ip.split(".")
    if len(parts) != 4:
        continue

    subnet = ".".join(parts[:3])

    if subnet not in groups:
        groups[subnet] = []

    groups[subnet].append(dev)


# 6) Ping helper for latency
def ping_latency(ip: str):
    out = run(f"ping -c1 -W1 {ip}")
    if not out:
        return None
    for line in out.splitlines():
        if "time=" in line:
            try:
                val = line.split("time=")[1].split()[0]
                return float(val)
            except:
                return None
    return None


# 7) Print header
print("\n[ YOU ]")
print(f" ├── Your IP: {my_ip}")
print(f" ├── Your Subnet: {my_subnet}.x")
print(f" ├── Connected SSID: {ssid or 'unknown'}")
print(f" ├── Access Point (BSSID): {bssid or 'unknown'}")
print(f" └── Gateway: {gw_ip}  (MAC: {gw_mac}, Vendor: {gw_vendor})\n")


# 8) Print tree per subnet
for subnet, dev_list in groups.items():
    count = len(dev_list)
    percent = round((count / 256) * 100, 2)

    if count < 3:
        tag = "  (Sparse)"
    elif count > 80:
        tag = "  (Heavy)"
    else:
        tag = ""

    subnet_mark = "  <== YOUR SUBNET" if subnet == my_subnet else ""

    print(f"     ├── {subnet}.x  ({count} hosts, {percent}% used){tag}{subnet_mark}")

    # choose a device with PING source to measure subnet latency
    sample = None
    for d in dev_list:
        if "PING" in d["sources"]:
            sample = d["ip"]
            break
    if sample is None:
        sample = dev_list[0]["ip"]

    latency = ping_latency(sample)
    if latency is not None:
        print(f"     │    Avg latency (sample {sample}): {latency} ms")

    # sort numerically by host octet
    dev_list_sorted = sorted(dev_list, key=lambda d: int(d["ip"].split(".")[3]))

    for dev in dev_list_sorted:
        ip = dev["ip"]
        mac = dev["mac"] or "unknown"
        srcs = dev["sources"]

        if srcs == {"PING"}:
            src_label = "PING"
        elif srcs == {"ARP"}:
            src_label = "ARP"
        else:
            src_label = "PING+ARP"

        you = "  (YOU)" if ip == my_ip else ""

        new_tag = "  (NEW)" if dev.get("is_new") else ""

        vendor = memory.get(mac, {}).get("vendor", "unknown vendor")

        print(
            f"     │\n"
            f"     │  └── {ip} [src={src_label}, mac={mac}, vendor={vendor}]{you}{new_tag}"
        )


# 9) Summary
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
        vendor = entry.get("vendor", "unknown")
        mac = entry.get("mac", "unknown")
        last_seen = entry.get("last_seen", 0)
        age_min = int((time.time() - last_seen) / 60)

        print(
            f"  └── {last_ip}  [MAC={mac}, vendor={vendor}, offline {age_min} min ago]"
        )

    print("----------------------------\n")
else:
    print(" No offline devices.")
    print("----------------------------\n")
