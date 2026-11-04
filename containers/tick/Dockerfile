# farglow-tick: The deterministic tick engine (hourly; every 5 minutes in DEBUG)
# Conventions (CLAUDE.md "Containers"): base pinned by digest, exact pins, wheels only,
# pip removed from the runtime image, non-root uid 1000, Python health check, build
# context = repository root.
FROM python:3.13-slim@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY containers/tick/requirements.txt /tmp/requirements.txt
# Optional extra CA for a TLS-intercepting proxy (build.sh: FARGLOW_BUILD_CA_FILE). It is a
# BuildKit secret, so it never lands in a layer.
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi \
    && pip install --no-cache-dir --root-user-action=ignore --only-binary=:all: -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && python -m pip uninstall -y pip

RUN groupadd -g 1000 farglow \
    && useradd -u 1000 -g farglow -M -d /app -s /usr/sbin/nologin farglow

WORKDIR /app
COPY VERSION /app/VERSION
COPY migrations /app/migrations
COPY config /app/config
COPY farglow /app/farglow
COPY containers/tick/healthcheck.py /usr/local/bin/healthcheck.py

USER farglow
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/usr/local/bin/healthcheck.py"]
CMD ["python", "-m", "farglow.engine.clock"]

# Build metadata LAST: it changes on every build, so every layer above stays cached
# (build.sh also skips an image whose inputs are unchanged: scripts/inputs.py).
ARG FARGLOW_BUILD=0.0.0+local
ARG FARGLOW_REVISION=unknown
ARG FARGLOW_CREATED=unknown
ARG FARGLOW_INPUTS=unknown
LABEL org.opencontainers.image.title="farglow-tick" \
      org.opencontainers.image.description="The deterministic tick engine (hourly; every 5 minutes in DEBUG)" \
      org.opencontainers.image.version="${FARGLOW_BUILD}" \
      org.opencontainers.image.revision="${FARGLOW_REVISION}" \
      org.opencontainers.image.created="${FARGLOW_CREATED}" \
      org.opencontainers.image.source="https://github.com/ennissh/farglow" \
      org.opencontainers.image.vendor="Citus Technologies, LLC" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.farglow.inputs="${FARGLOW_INPUTS}"
ENV FARGLOW_BUILD=${FARGLOW_BUILD}
