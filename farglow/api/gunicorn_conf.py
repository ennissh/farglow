"""Gunicorn settings for the api service (behind nginx on the private network)."""
import os

bind = "0.0.0.0:8000"
workers = int(os.environ.get("FARGLOW_WEB_WORKERS", "2"))
threads = int(os.environ.get("FARGLOW_WEB_THREADS", "4"))
worker_tmp_dir = "/tmp"
timeout = 60
graceful_timeout = 20
keepalive = 5
accesslog = "-"
errorlog = "-"
access_log_format = '{"ts":"%(t)s","service":"api","logger":"access","method":"%(m)s","path":"%(U)s","status":%(s)s,"bytes":"%(B)s","ms":%(M)s,"ip":"%({x-real-ip}i)s"}'
forwarded_allow_ips = "*"  # only nginx can reach this port (edge network)
