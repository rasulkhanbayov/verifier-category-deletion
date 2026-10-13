#!/bin/bash
STALL_SECS=1800  # 30 min -- 72B is legitimately slow (~15s/call), so
                  # checkpoints (every 25 instances) are naturally far
                  # apart; don't false-alarm on normal 72B pacing.
LOG="logs/qwen_resume2.log"
last_size=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
last_change=$(date +%s)
while pgrep -f run_qwen_resume2.sh > /dev/null; do
  sleep 120
  cur_size=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
  now=$(date +%s)
  if [ "$cur_size" != "$last_size" ]; then
    last_size=$cur_size
    last_change=$now
  elif [ $((now - last_change)) -gt $STALL_SECS ]; then
    echo "STALL DETECTED: $LOG has not grown in $((now - last_change))s"
    exit 1
  fi
done
echo "job finished (process no longer running)"
