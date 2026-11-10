#ifndef NAT64_H
#define NAT64_H

#include <stdint.h>
#include <netinet/ip.h>
#include <netinet/ip6.h>
#include <arpa/inet.h>

// 计算 IPv4 头部校验和
uint16_t ip_checksum(void *data, int len);

// IPv6 转 IPv4
int ipv6_to_ipv4(const uint8_t *in_pkt, int in_len, uint8_t *out_pkt, int out_cap);

// IPv4 转 IPv6
int ipv4_to_ipv6(const uint8_t *in_pkt, int in_len, uint8_t *out_pkt, int out_cap);

#endif
