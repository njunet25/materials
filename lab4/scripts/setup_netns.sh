#!/bin/bash
set -e

NS_C="ns_client"
NS_S="ns_server"
VETH_C="veth_c"
VETH_S="veth_s"
IP_C="10.10.0.1"
IP_S="10.10.0.2"

sudo ip netns del $NS_C 2>/dev/null || true
sudo ip netns del $NS_S 2>/dev/null || true

sudo ip netns add $NS_C
sudo ip netns add $NS_S

sudo ip link add $VETH_C type veth peer name $VETH_S
sudo ip link set $VETH_C netns $NS_C
sudo ip link set $VETH_S netns $NS_S

sudo ip netns exec $NS_C ip addr add $IP_C/24 dev $VETH_C
sudo ip netns exec $NS_S ip addr add $IP_S/24 dev $VETH_S

sudo ip netns exec $NS_C ip link set lo up
sudo ip netns exec $NS_S ip link set lo up
sudo ip netns exec $NS_C ip link set $VETH_C up
sudo ip netns exec $NS_S ip link set $VETH_S up

sudo ip netns exec $NS_C tc qdisc add dev $VETH_C root netem \
    delay 25ms loss 1% rate 20mbit
sudo ip netns exec $NS_S tc qdisc add dev $VETH_S root netem \
    delay 25ms

echo "===================================="
echo "Network environment ready."
echo "  Client: $NS_C ($IP_C)"
echo "  Server: $NS_S ($IP_S)"
echo "  Netem : delay 25ms loss 1% rate 20mbit"
echo "===================================="
