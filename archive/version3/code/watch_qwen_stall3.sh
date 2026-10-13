#!/bin/bash
STALL_SECS=300
LOG="logs/qwen_seeds_resume3.log"
last_size=$(stat -c %s "$LOG" 2>/dev/null || echo 0)
last_change=$(date +%s)
while pgrep -f run_qwen_seeds_resume3.sh > /dev/null; do
  sleep 30
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
