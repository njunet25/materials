#!/bin/bash
set -e

meson compile -C build bpf_cc.o
sudo bpftool struct_ops unregister name bpf_cc 2>/dev/null || true
sudo bpftool struct_ops register build/bpf_cc.o

# 等 struct_ops 在内核里生效
sleep 1

echo ""
echo "=== struct_ops show ==="
sudo bpftool struct_ops show
echo ""
echo "=== available congestion control ==="
sysctl net.ipv4.tcp_available_congestion_control
