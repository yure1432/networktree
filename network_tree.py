import subprocess

#  LOAD IPs FROM alive.txt
with open("alive.txt") as f:
    ips = [line.strip() for line in f if line.strip()]

#  GROUP IPs BY SUBNET
groups = {}

for ip in ips:
    parts = ip.split(".")
    subnet = ".".join(parts[:3])
    host = parts[3]

    if subnet not in groups:
        groups[subnet] = []

    groups[subnet].append(host)

#  FIND DEFAULT GATEWAY
gw_line = (
    subprocess.check_output("ip route | grep default", shell=True).decode().strip()
)
gw_ip = gw_line.split()[2] if gw_line else "unknown"

#  FIND GATEWAY MAC + VENDOR (IF POSSIBLE)
try:
    gw_mac = (
        subprocess.check_output(f"ip neigh | grep {gw_ip}", shell=True)
        .decode()
        .split()[4]
    )

    vendor = (
        subprocess.check_output(
            f"grep -i {gw_mac[:8].replace(':', '')} /usr/share/hwdata/oui.txt",
            shell=True,
        )
        .decode()
        .strip()
    )

except:
    gw_mac = "unknown"
    vendor = "unknown vendor"

#  DETECT YOUR OWN IP & SUBNET
my_ip = (
    subprocess.check_output("ip route get 1.1.1.1 | awk '{print $7}'", shell=True)
    .decode()
    .strip()
)

my_subnet = ".".join(my_ip.split(".")[:3])

#  WI-FI ACCESS POINT INFO (SSID + BSSID)
try:
    iw = subprocess.check_output("iw dev wlan0 link", shell=True).decode()
except:
    iw = ""

ssid = ""
bssid = ""

for line in iw.split("\n"):
    if "SSID" in line:
        ssid = line.split(":")[1].strip()
    if "Connected to" in line:
        bssid = line.split("Connected to")[1].strip()


#  FUNCTION: GET AVG PING FOR A SUBNET
def avg_ping(ip):
    try:
        out = subprocess.check_output(f"ping -c1 -W1 {ip}", shell=True).decode()
        for line in out.split("\n"):
            if "time=" in line:
                return float(line.split("time=")[1].split(" ")[0])
    except:
        return None


#  PRINT NETWORK TREE
print("\n[ YOU ]")
print(f" ├── Your IP: {my_ip}")
print(f" ├── Your Subnet: {my_subnet}.x")
print(f" ├── Connected SSID: {ssid or 'unknown'}")
print(f" ├── Access Point (BSSID): {bssid or 'unknown'}")
print(f" └── Gateway: {gw_ip}  (MAC: {gw_mac}, Vendor: {vendor})\n")

for subnet in groups:
    count = len(groups[subnet])
    percent = round((count / 256) * 100, 2)

    # detect strange subnets
    if count < 3:
        tag = "  (Sparse)"
    elif count > 80:
        tag = "  (Heavy)"
    else:
        tag = ""

    # highlight your subnet
    subnet_mark = "  <== YOUR SUBNET" if subnet == my_subnet else ""

    print(f"     ├── {subnet}.x  ({count} hosts, {percent}% used){tag}{subnet_mark}")

    # avg latency
    sample_ip = f"{subnet}.{groups[subnet][0]}"
    latency = avg_ping(sample_ip)
    if latency:
        print(f"     │    Avg latency: {latency} ms")

    # list hosts
    for host in sorted(groups[subnet], key=lambda x: int(x)):
        full_ip = f"{subnet}.{host}"

        if full_ip == my_ip:
            print(f"     │    └── {full_ip}  (YOU)")
        else:
            print(f"     │    └── {full_ip}")

#  SUMMARY
total_hosts = len(ips)
num_subnets = len(groups)

print("\n----------------------------")
print(" Network Summary")
print("----------------------------")
print(f" Total reachable hosts: {total_hosts}")
print(f" Total subnets active: {num_subnets}")
print("----------------------------\n")
