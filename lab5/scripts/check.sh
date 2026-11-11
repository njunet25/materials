#!/usr/bin/env bash
set -euo pipefail

case ${1:-env} in
    env)
        missing=0
        for command in ip ping nft tcpdump curl node ss; do
            if command -v "$command" >/dev/null; then
                echo "OK: $command"
            else
                echo "MISSING: $command" >&2
                missing=1
            fi
        done
        echo "Also check that IPv6 is enabled and Wireshark can open your pcap files."
        exit "$missing"
        ;;
    net)
        if (( EUID != 0 )); then
            echo "Run with sudo: sudo bash $0 ${1}" >&2
            exit 1
        fi
        for ns in lab5-c lab5-r1 lab5-r2 lab5-s; do
            if ! ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
                echo "Missing $ns; run setup_netns.sh first." >&2
                exit 1
            fi
        done
        ip netns exec lab5-c ping -4 -n -c 1 -W 3 10.5.3.2
        ip netns exec lab5-c ping -6 -n -c 1 -W 3 fd00:5:3::2
        ip netns exec lab5-c ping -4 -n -c 1 -W 3 -M probe -s 1372 10.5.3.2
        ip netns exec lab5-c ping -6 -n -c 1 -W 3 -M probe -s 1352 fd00:5:3::2
        echo "OK: IPv4/IPv6 connectivity and 1400-byte packets."
        ;;
    *)
        echo "Usage: bash $0 env | sudo bash $0 net" >&2
        exit 2
        ;;
esac
