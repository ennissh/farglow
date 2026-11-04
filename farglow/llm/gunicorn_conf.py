"""Gunicorn settings for the llm-gateway (internal only)."""
import os

bind = "0.0.0.0:8100"
workers = int(os.environ.get("FARGLOW_LLM_WORKERS", "2"))
threads = int(os.environ.get("FARGLOW_WEB_THREADS", "4"))
worker_tmp_dir = "/tmp"
timeout = 180
graceful_timeout = 20
keepalive = 5
accesslog = "-"
errorlog = "-"
access_log_format = '{"ts":"%(t)s","service":"llm-gateway","logger":"access","method":"%(m)s","path":"%(U)s","status":%(s)s,"bytes":"%(B)s","ms":%(M)s,"ip":"%({x-real-ip}i)s"}'
forwarded_allow_ips = "*"  # only nginx can reach this port (edge network)
