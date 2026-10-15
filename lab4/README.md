# Lab4: eBPF TCP Congestion Control

## Environment

- Linux kernel >= 5.6 (BTF, BPF STRUCT_OPS)
- clang, bpftool, meson, iproute2, iperf3

## Build

```bash
bpftool btf dump file /sys/kernel/btf/vmlinux format c > vmlinux.h
meson setup build
meson compile -C build bpf_cc.o
```

## Test

```bash
sudo ./scripts/setup_netns.sh
sudo ./scripts/register.sh
sudo ip netns exec ns_server iperf3 -s -p 5201 -D
sudo ip netns exec ns_client iperf3 -c 10.10.0.2 -p 5201 -C bpf_cc -t 15
```

## Cleanup

```bash
sudo bpftool struct_ops unregister name bpf_cc
sudo ./scripts/cleanup_netns.sh
```
