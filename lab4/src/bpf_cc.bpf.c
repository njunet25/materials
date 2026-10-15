// SPDX-License-Identifier: GPL-2.0
#include "bpf_cc.h"

#ifndef TCP_CONG_NON_RESTRICTED
#define TCP_CONG_NON_RESTRICTED 0x1
#endif

static __always_inline struct tcp_sock *tcp_sk(const struct sock *sk)
{
    return (struct tcp_sock *)sk;
}

SEC("struct_ops")
__u32 BPF_PROG(bpf_cc_ssthresh, struct sock *sk)
{
    const struct tcp_sock *tp = tcp_sk(sk);
    __u32 cwnd = cc_get_cwnd(tp);
    __u32 ssthresh = cwnd / 2;
    if (ssthresh < 10)
        ssthresh = 10;
    return ssthresh;
}

SEC("struct_ops")
void BPF_PROG(bpf_cc_cong_avoid, struct sock *sk, __u32 ack, __u32 acked)
{
    struct tcp_sock *tp = tcp_sk(sk);
    __u32 cwnd = cc_get_cwnd(tp);
    __u32 ssthresh = cc_get_ssthresh(tp);

    (void)ack;

    if (cwnd < ssthresh) {
        cwnd += acked;
        cc_set_cwnd(tp, cwnd);
    } else {
        __u32 cnt = cc_get_cwnd_cnt(tp);
        cnt += acked;
        if (cnt >= cwnd) {
            cnt -= cwnd;
            cwnd += 1;
            cc_set_cwnd(tp, cwnd);
        }
        cc_set_cwnd_cnt(tp, cnt);
    }
}

SEC("struct_ops")
__u32 BPF_PROG(bpf_cc_undo_cwnd, struct sock *sk)
{
    const struct tcp_sock *tp = tcp_sk(sk);
    return cc_get_cwnd(tp);
}

SEC("struct_ops")
void BPF_PROG(bpf_cc_init, struct sock *sk) { (void)sk; }

SEC("struct_ops")
void BPF_PROG(bpf_cc_release, struct sock *sk) { (void)sk; }

SEC(".struct_ops")
struct tcp_congestion_ops bpf_cc = {
    .name       = "bpf_cc",
    .flags      = TCP_CONG_NON_RESTRICTED,
    .init       = (void *)bpf_cc_init,
    .release    = (void *)bpf_cc_release,
    .ssthresh   = (void *)bpf_cc_ssthresh,
    .cong_avoid = (void *)bpf_cc_cong_avoid,
    .undo_cwnd  = (void *)bpf_cc_undo_cwnd,
};

char LICENSE[] SEC("license") = "GPL";
