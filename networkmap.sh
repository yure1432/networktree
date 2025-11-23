#!/bin/bash

# safer run: don't abort on first non-zero — we handle errors explicitly
# set -e

# 1) Find interface (more robust)
interface=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="dev") print $(i+1); exit}')
if [ -z "$interface" ]; then
  echo "[-] Could not determine active interface."
  exit 1
fi

echo "[*] Active interface: $interface"

# 2) IP/prefix
ip_with_prefix=$(ip -4 -o addr show dev "$interface" | awk '{for(i=1;i<=NF;i++) if ($i ~ /\/[0-9]+$/) print $4; exit}')

if [ -z "$ip_with_prefix" ]; then
  echo "[-] No IPv4 found on $interface."
  exit 1
fi

echo "[*] Detected address: $ip_with_prefix"

# 3) Network range via ipcalc (fallback to python if missing)
if command -v ipcalc >/dev/null 2>&1; then
  network_range=$(ipcalc "$ip_with_prefix" | awk '/Network/ {print $2; exit}')
else
  # fallback: compute network/CIDR using python ipaddress
  network_range=$(python3 - <<PY
import ipaddress, sys
s = "$ip_with_prefix"
net = ipaddress.ip_network(s, strict=False)
print(str(net))
PY
)
fi

if [ -z "$network_range" ]; then
  echo "[-] Could not determine network range."
  exit 1
fi

echo "[*] Scanning range: $network_range ..."

# 4) Run fping (and time it). If fping missing, warn and produce empty alive_ping.txt
start_fping=$(date +%s%3N)
if command -v fping >/dev/null 2>&1; then
  # redirect stderr so fping noise doesn't pollute output
  fping -a -q -g "$network_range" 2>/dev/null > alive_ping.txt || true
else
  echo "[-] fping not found. No ping results will be generated."
  # create empty file for main.py to read
  : > alive_ping.txt
fi
end_fping=$(date +%s%3N)
fping_time=$((end_fping - start_fping))
echo "[*] fping done. Time taken: ${fping_time} ms"

# 5) Export interface for the Python script (optional) and call Python
export INTERFACE="$interface"
python3 ~/networktree/main.py
