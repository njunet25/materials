#!/usr/bin/env python3
# clean_env.py —— 清理 lab4 全部网络命名空间
import subprocess
import sys

if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != "0":
    print("请用 sudo 运行：sudo python3 clean_env.py")
    sys.exit(1)

for ns in ["ns_a", "ns_gw", "ns_b"]:
    subprocess.run(["ip", "netns", "delete", ns], capture_output=True)

print("已清理全部网络命名空间：ns_a, ns_gw, ns_b")
