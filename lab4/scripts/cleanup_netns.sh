#!/bin/bash
sudo ip netns del ns_client 2>/dev/null || true
sudo ip netns del ns_server 2>/dev/null || true
echo "Cleaned up netns."
