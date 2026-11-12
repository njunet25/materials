# Lab5：分片与路径 MTU

使用 ping、curl 和 Wireshark 观察 IPv4 分片、IPv4/IPv6 的 PMTU 反馈，以及 TCP 对路径 MTU 变化的调整。
无需编写代码，只提交实验报告。操作步骤、观察要点和报告要求见实验手册。

需要 Linux、iproute2（含 ss）、iputils-ping、tcpdump、curl 和 Node.js。
Node.js 沿用 Lab2，只使用标准库，无需 npm 依赖。使用 Wireshark 打开抓包文件。

## 创建环境

在 `materials/lab5` 目录执行：

```sh
sudo bash scripts/setup_netns.sh
sudo ip netns exec lab5-c ping -4 -n -c 1 10.5.3.2
sudo ip netns exec lab5-c ping -6 -n -c 1 fd00:5:3::2
```

```text
lab5-c --1500-- lab5-r1 --1400-- lab5-r2 --1500-- lab5-s
```

脚本配置四个 network namespace 的双栈地址、路由与转发，无需公网或 NAT。
端系统关闭 TCP 自动黑洞探测，保留 ICMP 驱动的 PMTU 学习。
所有网络配置都位于实验 namespace 中，不要在其中运行无关任务。

## HTTP 服务与 MTU 调整

在单独终端启动服务器：

```sh
sudo ip netns exec lab5-s node server.mjs
```

服务监听 8000 端口：`/` 为小响应，`/large` 为 1 MiB，`/stream` 为约 26 秒的 16 MiB 响应。
每个响应结束后关闭连接。抓包和请求命令见手册。

持续传输期间，直接修改中间链路两端的 MTU：

```sh
sudo ip -n lab5-r1 link set dev right mtu 1300
sudo ip -n lab5-r2 link set dev left mtu 1300
```

将两条命令中的 `1300` 改为 `1400` 可恢复链路 MTU，但已学习的 PMTU 不一定立即升高。
虚拟接口卸载可能使抓包显示大于 MTU 的 TCP 报文；按手册结合 ICMP、ss 和传输结果判断。

## 清理

实验结束后，停止抓包和服务，再清理：

```sh
sudo bash scripts/cleanup_netns.sh
```

需要独立重做一组实验时，清理后重新运行 `setup_netns.sh`，以清除已学习的 PMTU。
清理会终止四个实验 namespace 中的进程并删除其网络配置。

## 选做思考题

1. 网络层已有 MTU 和 PMTU，为什么 TCP 还需要在握手中分别通告 MSS？两者分别约束什么，发送端如何同时满足这些约束？
2. 当 ICMP 差错反馈被过滤，出现小请求正常、大响应停滞的 PMTU 黑洞时，现代网络协议栈有哪些缓解机制？选择一至两种分析其原理、生效节点或传输方向及局限，并讨论握手时通告 MSS 是否足以应对连接中途的 PMTU 降低。

背景与完整题目见手册，无需额外搭建环境或实验。
