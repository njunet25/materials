#!/bin/bash
set -e

echo "[*] Cleaning up old environments..."
sudo ip netns del ns_client 2>/dev/null || true
sudo ip netns del ns_gateway 2>/dev/null || true
sudo ip netns del ns_server 2>/dev/null || true

echo "[*] Creating network namespaces..."
sudo ip netns add ns_client
sudo ip netns add ns_gateway
sudo ip netns add ns_server

sudo ip link add veth-client type veth peer name veth-gw1
sudo ip link add veth-gw2 type veth peer name veth-server

sudo ip link set veth-client netns ns_client
sudo ip link set veth-gw1 netns ns_gateway
sudo ip link set veth-gw2 netns ns_gateway
sudo ip link set veth-server netns ns_server

echo "[*] Configuring ns_client (IPv6 Only)..."
sudo ip netns exec ns_client ip link set lo up
sudo ip netns exec ns_client ip link set veth-client up
sudo ip netns exec ns_client ip addr add fd29:89ca:2902::1111/64 dev veth-client
sudo ip netns exec ns_client ip route add 64:ff9b::/96 via fd29:89ca:2902::1

echo "[*] Configuring ns_gateway (Dual Stack / NAT64)..."
sudo ip netns exec ns_gateway ip link set lo up
sudo ip netns exec ns_gateway ip link set veth-gw1 up
sudo ip netns exec ns_gateway ip addr add fd29:89ca:2902::1/64 dev veth-gw1
sudo ip netns exec ns_gateway ip link set veth-gw2 up
sudo ip netns exec ns_gateway ip addr add 100.64.0.1/10 dev veth-gw2
# Enable forwarding
sudo ip netns exec ns_gateway sysctl -w net.ipv4.ip_forward=1 > /dev/null
sudo ip netns exec ns_gateway sysctl -w net.ipv6.conf.all.forwarding=1 > /dev/null

echo "[*] Configuring ns_server (IPv4 Only)..."
sudo ip netns exec ns_server ip link set lo up
sudo ip netns exec ns_server ip link set veth-server up
sudo ip netns exec ns_server ip addr add 100.64.0.2/10 dev veth-server
sudo ip netns exec ns_server ip route add default via 100.64.0.1

# Make sure TUN device exists in ns_gateway (if nat64 program isn't running, we need a dummy route)
sudo ip netns exec ns_gateway ip tuntap add dev nat64 mode tun 2>/dev/null || true
sudo ip netns exec ns_gateway ip link set nat64 up
sudo ip netns exec ns_gateway ip -6 route add 64:ff9b::/96 dev nat64 2>/dev/null || true
sudo ip netns exec ns_gateway ip route add 100.64.0.0/10 dev nat64 2>/dev/null || true

echo "[+] Network environments ready."
