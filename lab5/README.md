# Lab5

纯观察实验：分片、PMTU 反馈、正常 TCP 自动调整，以及一个只在用户路由器修复 HTTP 的 challenge。
无需编写代码，只提交实验报告。手册包含原理、抓包位置、操作步骤与问题。

需要 iproute2、iputils-ping、nftables、tcpdump、curl、Node.js 和 `ss`。
Node.js 沿用 Lab2，只使用标准库，无需 npm 依赖。Wireshark 可在宿主机打开抓包。
下文命令均在 `materials/lab5` 或材料包解压后的 `lab5` 中执行。

```sh
bash scripts/check.sh env
sudo bash scripts/setup_netns.sh
sudo bash scripts/check.sh net
```

## 拓扑

```text
lab5-c --1500-- lab5-r1 --1400-- lab5-r2 --1500-- lab5-s
```

| 节点 | 接口 | IPv4 | IPv6 |
| --- | --- | --- | --- |
| lab5-c | eth0 | 10.5.1.2/24 | fd00:5:1::2/64 |
| lab5-r1 | left | 10.5.1.1/24 | fd00:5:1::1/64 |
| lab5-r1 | right | 10.5.2.1/24 | fd00:5:2::1/64 |
| lab5-r2 | left | 10.5.2.2/24 | fd00:5:2::2/64 |
| lab5-r2 | right | 10.5.3.1/24 | fd00:5:3::1/64 |
| lab5-s | eth0 | 10.5.3.2/24 | fd00:5:3::2/64 |

脚本配置双栈地址、往返路由和转发，不需要公网或 NAT。
新建接口关闭 DAD 以避免初始化等待；端系统关闭 TCP 自动黑洞探测，保留 ICMP 驱动的 PMTU 学习。
`setup_netns.sh` 不覆盖已有同名 namespace，失败时清理本次创建的节点。

## 正常观察

先按手册比较 IPv4 分片、DF 错误、IPv6 Packet Too Big，以及本地拒绝发送与网络返回错误。
`ping -M probe` 绕过已缓存 PMTU 的尺寸检查，仍受本地出接口 MTU 限制。

重建环境后，在单独终端启动 HTTP 服务：

```sh
sudo ip netns exec lab5-s node server.mjs
```

入口：`/` 为小响应，`/large` 为 1 MiB 响应，`/stream` 为约 26 秒的 16 MiB 响应。
每个响应结束后关闭连接。服务监听 8000 端口，支持 IPv4/IPv6。

先抓包再请求 `/large`，观察首次 PMTU 反馈。随后请求 `/stream`：

```sh
sudo ip netns exec lab5-c curl --max-time 45 \
  -o /dev/null http://10.5.3.2:8000/stream
```

传输期间，从另一个终端记录状态，降低中间 MTU，再记录状态：

```sh
sudo ip netns exec lab5-s ss -tin 'sport = :8000'
sudo bash scripts/set_link_mtu.sh 1300
sudo ip netns exec lab5-s ss -tin 'sport = :8000'
```

脚本只修改中间链路两端，接受 1280..1500；`set_link_mtu.sh 1400` 恢复链路 MTU。
恢复较大的链路 MTU 不代表已缓存的 PMTU 立即升高。独立对照直接重建拓扑。
`check.sh net` 检查默认 1400 拓扑，降低中间 MTU 后不应使用它判定默认环境是否正常。

## Challenge

```sh
sudo bash scripts/challenge.sh
```

该命令会重建拓扑，清除此前学到的 PMTU，停止旧的 HTTP 服务。
需要重新运行上面的 HTTP 启动命令。

challenge 的服务器配置使双向 ping、小 HTTP 响应正常，而较大的响应挂起。
可以只读检查任意节点，保持客户端、服务器和 r2 的配置不变，通过调整 r1 修复传输，具体方法不限。
具体诊断、修复证据和适用范围要求见手册。

## 清理和重做

先停止抓包，再运行：

```sh
sudo bash scripts/cleanup_netns.sh
```

清理会终止四个实验 namespace 中的进程，并删除其接口、路由和规则。
独立对照使用 `cleanup_netns.sh` 后再 `setup_netns.sh`；challenge 使用 `challenge.sh`。
不要在这四个 namespace 中运行无关任务。脚本不清空宿主机防火墙。
