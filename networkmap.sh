#!/bin/bash

interface=$(ip route get 1.1.1.1 | awk '{print $5}')

ip_with_prefix=$(ip -4 addr show dev "$interface" | awk '/inet /{print $2}')

network_range=$(ipcalc "$ip_with_prefix" | grep -w Network | awk '{print $2}')

fping -a -q -g "$network_range" 2>/dev/null > alive.txt

python3.13 ~/network_terminal_tree_map/network_tree.py
