#!/bin/bash

set -e

# 1) Find interface
interface=$(ip route get 1.1.1.1 | awk '{for (i=1;i<=NF;i++) if ($i=="dev") print $(i+1)}')

if [ -z "$interface" ]; then
  echo "[-] Could not determine active interface."
  exit 1
fi

echo "[*] Active interface: $interface"

# 2) IP/prefix
ip_with_prefix=$(ip -4 addr show dev "$interface" | awk '/inet / {print $2; exit}')

if [ -z "$ip_with_prefix" ]; then
  echo "[-] No IPv4 found on $interface."
  exit 1
fi

echo "[*] Detected address: $ip_with_prefix"

# 3) Network range via ipcalc
network_range=$(ipcalc "$ip_with_prefix" | awk '/Network/ {print $2; exit}')
echo "[*] Scanning range: $network_range ..."

# 4) Run fping (and time it)
start_fping=$(date +%s%3N)

fping -a -q -g "$network_range" 2>/dev/null > alive_ping.txt || true

end_fping=$(date +%s%3N)
fping_time=$((end_fping - start_fping))

echo "[*] fping done. Time taken: ${fping_time} ms"

# 5) Call Python
python3.13 /home/bartmoss/network_terminal_tree_map/main.py
