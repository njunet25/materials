#!/bin/bash
# setup-lab4.sh —— 搭建 lab4 虚拟网络拓扑
# 用法：sudo bash setup-lab4.sh
set -e

if [ "$EUID" -ne 0 ]; then
    echo "请用 sudo 运行：sudo bash setup-lab4.sh"
    exit 1
fi

# 清理旧命名空间
for ns in ns_a ns_gw ns_b; do
    ip netns delete "$ns" 2>/dev/null || true
done

# 清理可能残留的 veth
for l in veth_a veth_b; do
    ip link delete "$l" 2>/dev/null || true
done

# 创建网络命名空间
ip netns add ns_a
ip netns add ns_gw
ip netns add ns_b

# ns_a <--veth_a/veth_gw_a--> ns_gw
ip link add veth_a type veth peer name veth_gw_a
ip link set veth_a netns ns_a
ip link set veth_gw_a netns ns_gw

# ns_b <--veth_b/veth_gw_b--> ns_gw
ip link add veth_b type veth peer name veth_gw_b
ip link set veth_b netns ns_b
ip link set veth_gw_b netns ns_gw

# 配置 IP 并启用
ip netns exec ns_a ip addr add 10.0.1.10/24 dev veth_a
ip netns exec ns_a ip link set veth_a up
ip netns exec ns_a ip link set lo up

ip netns exec ns_gw ip addr add 10.0.1.1/24 dev veth_gw_a
ip netns exec ns_gw ip link set veth_gw_a up
ip netns exec ns_gw ip addr add 10.0.2.1/24 dev veth_gw_b
ip netns exec ns_gw ip link set veth_gw_b up
ip netns exec ns_gw ip link set lo up

ip netns exec ns_b ip addr add 10.0.2.10/24 dev veth_b
ip netns exec ns_b ip link set veth_b up
ip netns exec ns_b ip link set lo up

# 网关开启 IP 转发
ip netns exec ns_gw sysctl -w net.ipv4.ip_forward=1

# 配置默认网关
ip netns exec ns_a ip route add default via 10.0.1.1
ip netns exec ns_b ip route add default via 10.0.2.1

echo "拓扑搭建完成！"
echo "连通性测试：sudo ip netns exec ns_a ping 10.0.2.10 -c 2"
echo "实验结束清理：sudo python3 clean_env.py"
