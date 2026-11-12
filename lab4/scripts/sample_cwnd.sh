#!/bin/bash
# 用法: ./sample_cwnd.sh <namespace> <duration_sec> <output.csv>

NS=$1
DURATION=$2
OUTPUT=$3

if [ -z "$NS" ] || [ -z "$DURATION" ] || [ -z "$OUTPUT" ]; then
    echo "Usage: $0 <namespace> <duration_sec> <output.csv>"
    exit 1
fi

echo "timestamp,cwnd,ssthresh" > $OUTPUT

END=$((SECONDS + DURATION))
while [ $SECONDS -lt $END ]; do
    TS=$(date +%s.%N)
    LINE=$(sudo ip netns exec $NS ss -tin state established \
        '( dport = :5201 or sport = :5201 )' 2>/dev/null \
        | grep -m1 'bpf_cc' || true)
    # 用空格分词，逐字段精确匹配，避免 rcv_ssthresh 被误抓
    CWND=$(echo "$LINE" | tr ' ' '\n' | grep '^cwnd:' | head -1 | cut -d: -f2)
    SSTHRESH=$(echo "$LINE" | tr ' ' '\n' | grep '^ssthresh:' | head -1 | cut -d: -f2)
    CWND=${CWND:-0}
    SSTHRESH=${SSTHRESH:-0}
    echo "$TS,$CWND,$SSTHRESH" >> $OUTPUT
    sleep 0.2
done

echo "Saved to $OUTPUT"
