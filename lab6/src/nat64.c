#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <linux/if.h>
#include <linux/if_tun.h>
#include "nat64.h"

#define GATEWAY_IPV4 "100.64.0.1"
#define CLIENT_IPV6 "fd29:89ca:2902::1111"

uint16_t ip_checksum(void *data, int len) {
    uint32_t sum = 0;
    uint16_t *ptr = (uint16_t *)data;
    while (len > 1) { sum += *ptr++; len -= 2; }
    if (len == 1) sum += *(uint8_t *)ptr;
    while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
    return ~sum;
}

int ipv6_to_ipv4(const uint8_t *in_pkt, int in_len, uint8_t *out_pkt, int out_cap) {
    (void)in_len;
    struct ip6_hdr *ip6 = (struct ip6_hdr *)in_pkt;
    struct iphdr *ip4 = (struct iphdr *)out_pkt;

    // ==========================================
    // 提示：in_pkt 和 out_pkt 可能是同一块内存！
    // 请务必在 memset 之前，先把需要的字段提取到局部变量中！
    // ==========================================

    // TODO 1: 提取 IPv4 目的地址 (ip6->ip6_dst.s6_addr 的最后 4 字节)
    // TODO 2: 构造 IPv4 头部 (version, ihl, ttl, protocol, saddr, daddr, tot_len)
    // TODO 3: 计算 IP 校验和
    // TODO 4: 拷贝 Payload (注意：源偏移 40 字节，目标偏移 20 字节)

    return -1; // 请替换为实际转换后的长度
}

int ipv4_to_ipv6(const uint8_t *in_pkt, int in_len, uint8_t *out_pkt, int out_cap) {
    (void)in_len;
    struct iphdr *ip4 = (struct iphdr *)in_pkt;
    struct ip6_hdr *ip6 = (struct ip6_hdr *)out_pkt;

    // TODO 5: 提前保存字段
    // TODO 6: 构造 IPv6 头部并合成地址 (前缀 64:ff9b:: + ip4->saddr)
    // TODO 7: 拷贝 Payload (注意：源偏移 20 字节，目标偏移 40 字节，必须用 memmove！)

    return -1; // 请替换为实际转换后的长度
}

// ==========================================
// 以下为 main 函数，无需修改
// ==========================================
int main() {
    int tun_fd = open("/dev/net/tun", O_RDWR);
    if (tun_fd < 0) { perror("open tun"); return 1; }
    struct ifreq ifr = {0};
    ifr.ifr_flags = IFF_TUN | IFF_NO_PI;
    strncpy(ifr.ifr_name, "nat64", IFNAMSIZ);
    if (ioctl(tun_fd, TUNSETIFF, &ifr) < 0) { perror("ioctl"); return 1; }

    int raw_fd = socket(AF_INET, SOCK_RAW, IPPROTO_RAW);
    int on = 1;
    setsockopt(raw_fd, IPPROTO_IP, IP_HDRINCL, &on, sizeof(on));

    char buf[65536];
    printf("[NAT64] Running... tun_fd=%d, raw_fd=%d\n", tun_fd, raw_fd);

    int max_fd = (tun_fd > raw_fd) ? tun_fd : raw_fd;

    while (1) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(tun_fd, &fds);
        FD_SET(raw_fd, &fds);
        
        if (select(max_fd + 1, &fds, NULL, NULL, NULL) < 0) break;

        if (FD_ISSET(tun_fd, &fds)) {
            int n = read(tun_fd, buf, sizeof(buf));
            if (n > 0) {
                printf("[DEBUG] Got IPv6 packet from TUN, len=%d\n", n);
                int out_len = ipv6_to_ipv4((uint8_t*)buf, n, (uint8_t*)buf, sizeof(buf));
                if (out_len > 0) {
                    struct sockaddr_in dest = {0};
                    dest.sin_family = AF_INET;
                    memcpy(&dest.sin_addr, &((struct iphdr*)buf)->daddr, 4);
                    sendto(raw_fd, buf, out_len, 0, (struct sockaddr*)&dest, sizeof(dest));
                }
            }
        }
        
        if (FD_ISSET(raw_fd, &fds)) {
            int n = recv(raw_fd, buf, sizeof(buf), 0);
            if (n > 0) {
                struct iphdr *ip4 = (struct iphdr *)buf;
                if (ip4->saddr == inet_addr(GATEWAY_IPV4)) continue; 
                printf("[DEBUG] Got IPv4 packet from Raw Socket\n");
                int out_len = ipv4_to_ipv6((uint8_t*)buf, n, (uint8_t*)buf, sizeof(buf));
                if (out_len > 0) {
                    ssize_t w_ret = write(tun_fd, buf, out_len);
                    (void)w_ret; 
                }
            }
        }
    }
    return 0;
}
