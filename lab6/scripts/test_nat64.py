#!/usr/bin/env python3
import subprocess
import sys
import time
import os
import re

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
        print("[ERROR] Please run this script from the lab6 directory.")
        sys.exit(1)

    run("sudo ./scripts/setup_netns.sh")

    print("[INFO] Starting nat64 gateway in ns_gateway...")
    run("sudo ip netns exec ns_gateway ./nat64 > /tmp/nat64.log 2>&1 &")
    time.sleep(2)

    print("[INFO] Starting tcpdump on ns_server (Hex mode)...")
    run("sudo ip netns exec ns_server tcpdump -i veth-server -n -X -c 2 > /tmp/server_capture.log 2>&1 &")
    time.sleep(1)

    target = "64:ff9b::6440:0002"
    print(f"[INFO] Pinging {target} from ns_client...")
    run(f"sudo ip netns exec ns_client ping -6 -c 2 -W 2 {target}", check=False)

    time.sleep(1)
    run("sudo pkill tcpdump", check=False)

    print("\n=== Gateway Console Output (NAT64 Log) ===")
    print(run("cat /tmp/nat64.log", check=False))

    print("=== Server Capture Analysis (Hacker Mode) ===")
    capture_out = run("cat /tmp/server_capture.log", check=False)
    
    hex_blocks = re.findall(r'0x([0-9a-fA-F]{4}):\s+((?:[0-9a-fA-F]{4}\s+)+)', capture_out)
    
    parsed = False
    for addr, data in hex_blocks:
        hex_str = data.replace(' ', '')
        raw_bytes = bytes.fromhex(hex_str)
        if len(raw_bytes) >= 20 and raw_bytes[0] == 0x45:
            print(f"\033[1;36m[+] Captured IPv4 Packet on ns_server!\033[0m")
            print(f"    Version: {raw_bytes[0] >> 4}")
            print(f"    Header Length: {(raw_bytes[0] & 0x0F) * 4} bytes")
            print(f"    Total Length: {int.from_bytes(raw_bytes[2:4], 'big')} bytes")
            print(f"    TTL: {raw_bytes[8]}")
            print(f"    Protocol: {raw_bytes[9]} (58 = ICMPv6, 6 = TCP, 17 = UDP)")
            src_ip = ".".join(str(b) for b in raw_bytes[12:16])
            dst_ip = ".".join(str(b) for b in raw_bytes[16:20])
            print(f"    Source IP: {src_ip}")
            print(f"    Dest IP:   {dst_ip}")
            parsed = True
            break

    if not parsed or "100.64.0.1 > 100.64.0.2" not in capture_out:
        print("\n[FAIL] NAT64 translation failed. Packet did not reach ns_server correctly.")
        print("Check /tmp/nat64.log for debug info.")
        run("sudo pkill -f './nat64'", check=False)
        run("sudo ./scripts/cleanup_netns.sh", check=False)
        sys.exit(1)

    print("\n[PASS] NAT64 translation works. Packet successfully reached ns_server.")
    run("sudo pkill -f './nat64'", check=False)
    run("sudo ./scripts/cleanup_netns.sh", check=False)
    print("=== ALL TESTS PASSED ===")

if __name__ == "__main__":
    main()
