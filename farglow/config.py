"""Runtime settings, read once from the environment.

Every service gets only the variables it needs (compose.yaml maps them explicitly from
.env). A secret may also be given as <NAME>_FILE pointing at a file, the Docker secrets
convention, so a later move to file-based secrets needs no code change.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import quote


def env(name: str, default: str | None = None) -> str | None:
    file_path = os.environ.get(f"{name}_FILE")
    if file_path:
        with open(file_path, encoding="utf-8") as fh:
            return fh.read().strip()
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    value = env(name)
    return int(value) if value is not None else default


AI_TIERS = ("T0", "T1", "T2", "T3", "T4")


@dataclass(frozen=True)
class Settings:
    service: str = "farglow"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    db_host: str = "db"
    db_port: int = 5432
    db_name: str = "farglow"
    db_user: str = "farglow"
    db_password: str = ""

    # Public identity
    domain: str = "localhost"
    public_url: str = "http://localhost"
    admin_email: str = ""
    secret_key: str = ""
    link_signing_key: str = ""

    # Engine
    galaxy_seed: int = 0
    tick_seconds: int = 3600
    restore_points_keep: int = 72

    # AI
    ai_tier: str = "T0"
    llm_gateway_url: str = "http://llm-gateway:8100"
    llm_endpoint: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout: int = 30

    # Mail
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"  # starttls | ssl | none
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = ""

    extra: dict = field(default_factory=dict)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{quote(self.db_user, safe='')}:{quote(self.db_password, safe='')}"
            f"@{self.db_host}:{self.db_port}/{quote(self.db_name, safe='')}"
        )

    @property
    def mail_enabled(self) -> bool:
        return bool(self.smtp_host)


def load(service: str = "farglow") -> Settings:
    debug = env_bool("FARGLOW_DEBUG")
    tier = (env("FARGLOW_AI_TIER", "T0") or "T0").upper()
    if tier not in AI_TIERS:
        raise ValueError(f"FARGLOW_AI_TIER must be one of {', '.join(AI_TIERS)}, got {tier!r}")
    # Hourly in production, every 5 minutes in DEBUG; FARGLOW_TICK_SECONDS overrides both (tests).
    tick_default = 300 if debug else 3600
    domain = env("FARGLOW_DOMAIN", "localhost") or "localhost"
    return Settings(
        service=service,
        debug=debug,
        log_level=(env("FARGLOW_LOG_LEVEL", "DEBUG" if debug else "INFO") or "INFO").upper(),
        db_host=env("POSTGRES_HOST", "db"),
        db_port=env_int("POSTGRES_PORT", 5432),
        db_name=env("POSTGRES_DB", "farglow"),
        db_user=env("POSTGRES_USER", "farglow"),
        db_password=env("POSTGRES_PASSWORD", "") or "",
        domain=domain,
        public_url=(env("FARGLOW_PUBLIC_URL", f"http://{domain}") or "").rstrip("/"),
        admin_email=env("FARGLOW_ADMIN_EMAIL", "") or "",
        secret_key=env("FARGLOW_SECRET_KEY", "") or "",
        link_signing_key=env("FARGLOW_LINK_SIGNING_KEY", "") or "",
        galaxy_seed=env_int("FARGLOW_GALAXY_SEED", 0),
        tick_seconds=env_int("FARGLOW_TICK_SECONDS", tick_default),
        restore_points_keep=env_int("FARGLOW_RESTORE_POINTS_KEEP", 72),
        ai_tier=tier,
        llm_gateway_url=(env("FARGLOW_LLM_GATEWAY_URL", "http://llm-gateway:8100") or "").rstrip("/"),
        llm_endpoint=(env("FARGLOW_LLM_ENDPOINT", "") or "").rstrip("/"),
        llm_model=env("FARGLOW_LLM_MODEL", "") or "",
        llm_api_key=env("FARGLOW_LLM_API_KEY", "") or "",
        llm_timeout=env_int("FARGLOW_LLM_TIMEOUT", 30),
        smtp_host=env("SMTP_HOST", "") or "",
        smtp_port=env_int("SMTP_PORT", 587),
        smtp_security=(env("SMTP_SECURITY", "starttls") or "starttls").lower(),
        smtp_user=env("SMTP_USER", "") or "",
        smtp_password=env("SMTP_PASSWORD", "") or "",
        mail_from=env("SMTP_FROM", "") or "",
    )
