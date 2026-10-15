#ifndef __BPF_CC_H
#define __BPF_CC_H

#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

/* ============================================================
 * 预置读写辅助函数（学生不需要修改）
 * ============================================================ */

static __always_inline __u32 cc_get_cwnd(const struct tcp_sock *tp)
{
    return BPF_CORE_READ(tp, snd_cwnd);
}

static __always_inline void cc_set_cwnd(struct tcp_sock *tp, __u32 cwnd)
{
    tp->snd_cwnd = cwnd;
}

static __always_inline __u32 cc_get_ssthresh(const struct tcp_sock *tp)
{
    return BPF_CORE_READ(tp, snd_ssthresh);
}

static __always_inline __u32 cc_get_cwnd_cnt(const struct tcp_sock *tp)
{
    return BPF_CORE_READ(tp, snd_cwnd_cnt);
}

static __always_inline void cc_set_cwnd_cnt(struct tcp_sock *tp, __u32 cnt)
{
    tp->snd_cwnd_cnt = cnt;
}

#endif
