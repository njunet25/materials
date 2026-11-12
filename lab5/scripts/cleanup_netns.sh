#!/usr/bin/env bash
set -euo pipefail

if (( EUID != 0 )); then
    echo "Run with sudo: sudo bash $0" >&2
    exit 1
fi

for ns in lab5-c lab5-r1 lab5-r2 lab5-s; do
    if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
        mapfile -t pids < <(ip netns pids "$ns")
        if (( ${#pids[@]} )); then
            kill -TERM -- "${pids[@]}" 2>/dev/null || true
        fi
        ip netns del "$ns"
    fi
done
echo "Lab5 namespaces removed."
