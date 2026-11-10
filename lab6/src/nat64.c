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
#include <arpa/inet.h>
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

    char src6[INET6_ADDRSTRLEN], dst6[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &ip6->ip6_src, src6, sizeof(src6));
    inet_ntop(AF_INET6, &ip6->ip6_dst, dst6, sizeof(dst6));
    printf("\033[1;33m[NAT64 Outbound] IPv6: %s -> %s\033[0m\n", src6, dst6);
    fflush(stdout);

    // TODO 1: 提取 IPv4 目的地址 (ip6->ip6_dst.s6_addr 的最后 4 字节)
    // 提示：请先提前保存 next_hdr, payload_len, dst_ipv4，再 memset！
    uint32_t dst_ipv4 = 0; 
    int payload_len = ntohs(ip6->ip6_plen);

    char dst4[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &dst_ipv4, dst4, sizeof(dst4));
    printf("\033[1;32m              => Target IPv4: %s\033[0m\n", dst4);
    fflush(stdout);

    // TODO 2: 构造 IPv4 头部
    // TODO 3: 计算校验和
    // TODO 4: 拷贝 Payload (注意：源偏移 40 字节，目标偏移 20 字节)

    return -1; 
}

int ipv4_to_ipv6(const uint8_t *in_pkt, int in_len, uint8_t *out_pkt, int out_cap) {
    (void)in_len;
    struct iphdr *ip4 = (struct iphdr *)in_pkt;
    struct ip6_hdr *ip6 = (struct ip6_hdr *)out_pkt;

    // TODO 5: 构造 IPv6 头部并合成地址
    // TODO 6: 拷贝 Payload (必须用 memmove！)

    return -1; 
}

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
    printf("[NAT64] Gateway started. Waiting for packets...\n");
    fflush(stdout);

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
