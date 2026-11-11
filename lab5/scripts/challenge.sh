#!/usr/bin/env bash
set -euo pipefail
lab5_scripts=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

if (( EUID != 0 )); then
    echo "Run with sudo: sudo bash $0" >&2
    exit 1
fi
if (( $# != 0 )); then
    echo "Usage: sudo bash $0" >&2
    exit 2
fi

# A fresh topology removes PMTU learned during the normal experiments.
# This also stops the previous HTTP server; start it again afterwards.
bash "$lab5_scripts/cleanup_netns.sh"
bash "$lab5_scripts/setup_netns.sh"
ip netns exec lab5-s sysctl -qw net.ipv4.tcp_mtu_probing=0
ip netns exec lab5-s nft -f - <<'EOF'
table inet lab5_blackhole {
    chain input {
        type filter hook input priority 0; policy accept;
        icmp type destination-unreachable icmp code 4 counter drop
        icmpv6 type packet-too-big counter drop
    }
}
EOF

echo "Challenge ready. Restart server.mjs in lab5-s. Modify only lab5-r1 to repair."
