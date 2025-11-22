This document breaks down the entire Python script at the deepest level, explaining every command, concept, structure, and interaction with the Linux network stack.

-----------------------------------------------------
SECTION 1 — Loading Alive IPs
-----------------------------------------------------
The script opens the file “alive.txt”, produced by fping, where each line represents an IPv4 address that responded to ping. The list comprehension:

    ips = [line.strip() for line in f if line.strip()]

removes blank lines and whitespace. The resulting list is:

    ["10.53.36.20", "10.53.36.100", ...]

These are strings, each representing an alive host.

-----------------------------------------------------
SECTION 2 — Grouping IPs By Subnet
-----------------------------------------------------
Each IP is split by "." into ["10","53","36","100"].

The subnet is the first three octets:

    subnet = "10.53.36"

The host part is the last octet:

    host = "100"

A dictionary named “groups” uses subnet strings as keys. For each subnet, a list of hosts is stored:

    {
      "10.53.36": ["20", "100"],
      ...
    }

This lets the script render a hierarchical tree grouped by subnets.

-----------------------------------------------------
SECTION 3 — Discovering the Default Gateway
-----------------------------------------------------
The script runs:

    ip route | grep default

Typical output:

    default via 10.53.36.20 dev wlan0 proto dhcp metric 600

The third field is the gateway IP:

    gw_ip = "10.53.36.20"

This is the router that your traffic passes through.

-----------------------------------------------------
SECTION 4 — Gateway MAC Address + Vendor Lookup
-----------------------------------------------------
The script checks your ARP table:

    ip neigh | grep 10.53.36.20

Example output:

    10.53.36.20 dev wlan0 lladdr 32:18:26:c4:52:be REACHABLE

Field 4 is the MAC address:

    32:18:26:c4:52:be

The first three bytes (OUI prefix) identify the manufacturer. It searches:

    /usr/share/hwdata/oui.txt

If not found, the vendor is listed as "unknown".

-----------------------------------------------------
SECTION 5 — Detecting YOUR IP & Subnet
-----------------------------------------------------
The script uses:

    ip route get 1.1.1.1

Example output:

    1.1.1.1 via 10.53.36.20 dev wlan0 src 10.53.36.100

This command tells you:

- Which gateway is used
- Which interface is used
- MOST IMPORTANT: `src <your-ip>`

The script extracts field #7:

    my_ip = "10.53.36.100"

Your subnet:

    my_subnet = "10.53.36"

-----------------------------------------------------
SECTION 6 — Gathering WiFi AP Info (SSID + BSSID)
-----------------------------------------------------
It runs:

    iw dev wlan0 link

This prints:

    Connected to <BSSID>
    SSID: <WiFi-name>
    signal: ...

From this, the script extracts:

- SSID: the WiFi network name
- BSSID: the MAC address of the Access Point you are connected to

-----------------------------------------------------
SECTION 7 — Average Ping Function
-----------------------------------------------------
The function avg_ping() runs:

    ping -c1 -W1 <ip>

It looks for a line containing "time=XX ms":

    64 bytes from <ip>: time=4.58 ms

Then extracts the numeric time value. This gives a rough latency estimate for the subnet.

-----------------------------------------------------
SECTION 8 — Printing the Network Tree
-----------------------------------------------------
First it prints your local info:

[ YOU ]
 ├── Your IP
 ├── Your Subnet
 ├── SSID
 ├── BSSID
 └── Gateway + Vendor

Then for each subnet (e.g., "10.53.36"):

- Counts hosts in the subnet
- Computes percentage used (out of 256 possible IPs)
- Applies tags:
      (Sparse) if < 3 hosts
      (Heavy)  if > 80 hosts
- Highlights your subnet
- Computes latency by pinging the first alive host

-----------------------------------------------------
SECTION 9 — Listing Each Host
-----------------------------------------------------
For each host in the subnet:

- Hosts are sorted numerically (so 2 < 100)
- If host equals your IP, it prints "(YOU)"

Example:

    10.53.36.100  (YOU)

-----------------------------------------------------
SECTION 10 — Final Summary
-----------------------------------------------------
At the end, the script prints:

    Total reachable hosts
    Total active subnets

This provides a high-level view of the network.

-----------------------------------------------------
WHAT THE SCRIPT ACTUALLY DOES 
-----------------------------------------------------

• Automatically discovers:
  - Your IP
  - Your subnet
  - Your router (gateway)
  - Your WiFi access point’s MAC + SSID

• Uses fping + alive.txt to map which IPs are alive

• Groups hosts into subnet groups

• Calculates host density and subnet utilization

• Computes latency to representative hosts in each subnet

• Resolves gateway vendor through MAC OUI lookup

• Produces a visually structured network tree:
  - Subnets
  - Hosts
  - Your location within the topology

• Labels:
  - YOUR subnet
  - YOUR IP (YOU)
  - Sparse or Heavy subnets
  - Gateway, BSSID, SSID metadata
