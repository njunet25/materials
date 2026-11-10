#!/usr/bin/env python3
import subprocess
import sys
import time
import os

def run(cmd, check=True):
    print(f"[RUN] {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(r.stdout)
        print(r.stderr)
        print(f"[FAIL] Command failed: {cmd}")
        sys.exit(1)
    return r.stdout

def main():
    print("=== Starting NAT64 Test Suite ===")
    
    if not os.path.exists("./scripts/setup_netns.sh"):
        print("[ERROR] Please run this script from the lab6-dev directory.")
        sys.exit(1)

    run("sudo ./scripts/setup_netns.sh")

    print("[INFO] Starting nat64 gateway in ns_gateway...")
    run("sudo ip netns exec ns_gateway ./nat64 > /tmp/nat64.log 2>&1 &")
    time.sleep(2)

    # 在 ns_server 上启动 tcpdump，抓取是否有转换后的 IPv4 包到达
    print("[INFO] Starting tcpdump on ns_server...")
    run("sudo ip netns exec ns_server tcpdump -i veth-server -n ip > /tmp/server_capture.log 2>&1 &")
    time.sleep(1)

    target = "64:ff9b::6440:0002"
    print(f"[INFO] Pinging {target} from ns_client...")
    run(f"sudo ip netns exec ns_client ping -6 -c 4 -W 2 {target}", check=False)

    time.sleep(1)
    run("sudo pkill tcpdump", check=False)

    print("[INFO] Checking server capture...")
    capture_out = run("cat /tmp/server_capture.log", check=False)
    
    if "100.64.0.1 > 100.64.0.2" not in capture_out:
        print("\n[FAIL] NAT64 translation failed. Packet did not reach ns_server.")
        print("=== Server Capture ===")
        print(capture_out)
        print("Check /tmp/nat64.log for debug info.")
        run("sudo pkill -f './nat64'", check=False)
        run("sudo ./scripts/cleanup_netns.sh", check=False)
        sys.exit(1)

    print("\n[PASS] NAT64 translation works. Packet successfully reached ns_server.")
    print("=== Server Capture (IPv4 header converted) ===")
    print(capture_out)
    
    run("sudo pkill -f './nat64'", check=False)
    run("sudo ./scripts/cleanup_netns.sh", check=False)
    print("=== ALL TESTS PASSED ===")

if __name__ == "__main__":
    main()
