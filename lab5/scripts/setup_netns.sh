#!/usr/bin/env bash
set -euo pipefail

if (( EUID != 0 )); then
    echo "Run with sudo: sudo bash $0" >&2
    exit 1
fi

namespaces=(lab5-c lab5-r1 lab5-r2 lab5-s)
for ns in "${namespaces[@]}"; do
    if ip netns list | awk '{print $1}' | grep -Fxq "$ns"; then
        echo "Namespace $ns already exists; clean up the previous lab first." >&2
        exit 1
    fi
done

created=()
rollback() {
    for ns in "${created[@]}"; do
        ip netns del "$ns" || true
    done
}
trap rollback ERR

for ns in "${namespaces[@]}"; do
    ip netns add "$ns"
    created+=("$ns")
    # Link-local addresses also need to be ready before one-second probes.
    ip netns exec "$ns" sysctl -qw net.ipv6.conf.default.accept_dad=0
    ip -n "$ns" link set lo up
done

# Create each pair directly inside the lab namespaces.
ip -n lab5-c link add eth0 type veth peer name left netns lab5-r1
ip -n lab5-r1 link add right type veth peer name left netns lab5-r2
ip -n lab5-r2 link add right type veth peer name eth0 netns lab5-s

configure_link() {
    local ns=$1 iface=$2 mtu=$3 ipv4=$4 ipv6=$5
    ip -n "$ns" link set dev "$iface" mtu "$mtu" up
    ip -n "$ns" addr add "$ipv4" dev "$iface"
    # Static, unique lab addresses: skip DAD so the topology is ready on return.
    ip -n "$ns" -6 addr add "$ipv6" dev "$iface" nodad
}

configure_link lab5-c eth0 1500 10.5.1.2/24 fd00:5:1::2/64
configure_link lab5-r1 left 1500 10.5.1.1/24 fd00:5:1::1/64
configure_link lab5-r1 right 1400 10.5.2.1/24 fd00:5:2::1/64
configure_link lab5-r2 left 1400 10.5.2.2/24 fd00:5:2::2/64
configure_link lab5-r2 right 1500 10.5.3.1/24 fd00:5:3::1/64
configure_link lab5-s eth0 1500 10.5.3.2/24 fd00:5:3::2/64

for ns in lab5-r1 lab5-r2; do
    ip netns exec "$ns" sysctl -qw net.ipv4.ip_forward=1
    ip netns exec "$ns" sysctl -qw net.ipv6.conf.all.forwarding=1
done

# Keep PMTU learning ICMP-based rather than masking the challenge by TCP probing.
for ns in lab5-c lab5-s; do
    ip netns exec "$ns" sysctl -qw net.ipv4.tcp_mtu_probing=0
done

ip -n lab5-c route add default via 10.5.1.1
ip -n lab5-c -6 route add default via fd00:5:1::1
ip -n lab5-s route add default via 10.5.3.1
ip -n lab5-s -6 route add default via fd00:5:3::1
ip -n lab5-r1 route add 10.5.3.0/24 via 10.5.2.2
ip -n lab5-r1 -6 route add fd00:5:3::/64 via fd00:5:2::2
ip -n lab5-r2 route add 10.5.1.0/24 via 10.5.2.1
ip -n lab5-r2 -6 route add fd00:5:1::/64 via fd00:5:2::1

trap - ERR
echo "Lab5 ready: lab5-c --1500-- lab5-r1 --1400-- lab5-r2 --1500-- lab5-s"
