"""LLM gateway (Flask). AI models only PROPOSE JSON; the engine validates and decides.

POST /v1/propose {"task": "...", "prompt": "...", "context": {...}}
  -> {"tier": "T2", "fallback": false, "proposal": {...}, "latency_ms": 812}

Tiers: T0 templates (always available) · T1/T2 Ollama-compatible /api/chat · T3 an
OpenAI-compatible /chat/completions with the host's key · T4 the Relay (not available yet).
Any failure falls back to T0, so every caller works without AI.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from flask import Flask, jsonify, request

from .. import __version__, config
from .. import log as flog

log = logging.getLogger("farglow.llm")

T0_TEMPLATES = {
    "advisor.greeting": {"text": "Good morning. The overnight Dispatch is ready, and nothing needs you urgently."},
    "news.headline": {"text": "Quiet tick across the cell."},
}


class TierError(RuntimeError):
    pass


def t0(task: str, context: dict) -> dict:
    return dict(T0_TEMPLATES.get(task, {"text": ""}), template=True)


def _post_json(url: str, body: dict, timeout: int, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - host-configured URL
        return json.loads(resp.read())


def _object(text: str) -> dict:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TierError("model did not return a JSON object")
    return value


def call_tier(settings: config.Settings, task: str, prompt: str) -> dict:
    tier = settings.ai_tier
    if tier == "T0":
        raise TierError("T0 selected")
    if not settings.llm_endpoint:
        raise TierError(f"{tier} has no FARGLOW_LLM_ENDPOINT")
    system = "Reply with one JSON object only. You propose; the game engine decides."
    if tier in ("T1", "T2"):
        out = _post_json(f"{settings.llm_endpoint}/api/chat", {
            "model": settings.llm_model, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }, settings.llm_timeout)
        return _object(out["message"]["content"])
    if tier == "T3":
        out = _post_json(f"{settings.llm_endpoint}/chat/completions", {
            "model": settings.llm_model, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }, settings.llm_timeout, {"Authorization": f"Bearer {settings.llm_api_key}"})
        return _object(out["choices"][0]["message"]["content"])
    raise TierError("T4 (Relay) is not available yet")


def create_app(settings: config.Settings | None = None) -> Flask:
    settings = settings or config.load("llm-gateway")
    app = Flask(__name__)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", version=__version__)

    @app.get("/v1/status")
    def status():
        return jsonify(tier=settings.ai_tier, model=settings.llm_model or None,
                       endpoint_configured=bool(settings.llm_endpoint), version=__version__)

    @app.post("/v1/propose")
    def propose():
        body = request.get_json(silent=True) or {}
        task = str(body.get("task", ""))
        prompt = str(body.get("prompt", ""))
        context = body.get("context") or {}
        t = time.monotonic()
        tier, fallback, error = settings.ai_tier, False, None
        try:
            proposal = call_tier(settings, task, prompt)
        except (TierError, urllib.error.URLError, TimeoutError, OSError, KeyError, ValueError) as exc:
            proposal, fallback, error = t0(task, context), settings.ai_tier != "T0", str(exc)
            tier = "T0"
        ms = int((time.monotonic() - t) * 1000)
        log.info("propose", extra={"task": task, "tier": tier, "configured_tier": settings.ai_tier,
                                   "fallback": fallback, "latency_ms": ms, "error": error})
        return jsonify(tier=tier, fallback=fallback, proposal=proposal, latency_ms=ms)

    return app


def wsgi() -> Flask:
    settings = config.load("llm-gateway")
    flog.setup("llm-gateway", settings.log_level)
    return create_app(settings)
