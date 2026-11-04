#!/usr/bin/env python3
"""Container health check: the service loop touches /tmp/farglow-heartbeat; it must be fresh.

A stuck loop (deadlock, hung database call) stops touching the file and turns unhealthy.
"""
import os
import sys
import time

MAX_AGE_S = 120
try:
    age = time.time() - os.path.getmtime("/tmp/farglow-heartbeat")
except OSError:
    print("unhealthy: no heartbeat file yet")
    sys.exit(1)
if age > MAX_AGE_S:
    print(f"unhealthy: heartbeat {int(age)} s old")
    sys.exit(1)
sys.exit(0)
