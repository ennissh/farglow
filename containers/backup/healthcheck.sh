#!/bin/bash
# Healthy while the daemon loop keeps touching its heartbeat (every 60 s).
[[ -f /tmp/farglow-heartbeat ]] || { echo "no heartbeat yet"; exit 1; }
age=$(( $(date +%s) - $(cat /tmp/farglow-heartbeat) ))
(( age < 180 )) || { echo "heartbeat ${age}s old"; exit 1; }
