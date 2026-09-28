#!/bin/zsh
# Run a command, killing it on memory pressure, RSS > 85% of RAM, or 20 min wall time. macOS only.
# usage: ./watchdog.sh <logfile> <cmd...>    escape hatch: pkill -9 -f 'benchmarks/.venv/bin/python'
log=$1; shift
max_rss_kb=$(( $(sysctl -n hw.memsize) / 1024 * 85 / 100 ))
"$@" > "$log" 2>&1 &
pid=$!
echo "pid=$pid log=$log"
start=$SECONDS; peak=0; maxlvl=1
while kill -0 $pid 2>/dev/null; do
  lvl=$(sysctl -n kern.memorystatus_vm_pressure_level)  # 1 normal, 2 warn, 4 critical
  rss=$(ps -o rss= -p $pid 2>/dev/null | tr -d ' '); rss=${rss:-0}
  (( rss > peak )) && peak=$rss; (( lvl > maxlvl )) && maxlvl=$lvl
  if (( lvl > 1 || rss > max_rss_kb || SECONDS - start > 1200 )); then
    kill -9 $pid
    echo "WATCHDOG KILLED pid=$pid: pressure_level=$lvl rss_mb=$((rss / 1024)) elapsed=$((SECONDS - start))s" | tee -a "$log"
    exit 1
  fi
  sleep 0.2
done
wait $pid; rc=$?
echo "watchdog: rc=$rc peak_rss_mb=$((peak / 1024)) max_pressure_level=$maxlvl elapsed=$((SECONDS - start))s" | tee -a "$log"
exit $rc
