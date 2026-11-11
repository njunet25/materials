#!/usr/bin/env bash
set -euo pipefail

if (( EUID != 0 )); then
    echo "Run with sudo: sudo bash $0 MTU" >&2
    exit 1
fi
if [[ $# != 1 || ! $1 =~ ^[0-9]{4}$ ]]; then
    echo "Usage: sudo bash $0 MTU (1280..1500)" >&2
    exit 2
fi
lab5_mtu=$((10#$1))
if (( lab5_mtu < 1280 || lab5_mtu > 1500 )); then
    echo "MTU must be between 1280 and 1500." >&2
    exit 2
fi
# Check both interfaces before changing either side.
ip -n lab5-r1 link show dev right >/dev/null
ip -n lab5-r2 link show dev left >/dev/null
ip -n lab5-r1 link set dev right mtu "$lab5_mtu"
ip -n lab5-r2 link set dev left mtu "$lab5_mtu"
echo "Middle link MTU: $lab5_mtu (both ends); endpoint interfaces unchanged."
