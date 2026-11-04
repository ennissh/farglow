# farglow-__NAME__: __TITLE__
# Conventions (CLAUDE.md "Containers"): base pinned by digest, exact pins, wheels only,
# pip removed from the runtime image, non-root uid 1000, Python health check, build
# context = repository root.
FROM __PYBASE__

ARG FARGLOW_BUILD=0.0.0+local
ARG FARGLOW_REVISION=unknown
ARG FARGLOW_CREATED=unknown
LABEL org.opencontainers.image.title="farglow-__NAME__" \
      org.opencontainers.image.description="__TITLE__" \
      org.opencontainers.image.version="${FARGLOW_BUILD}" \
      org.opencontainers.image.revision="${FARGLOW_REVISION}" \
      org.opencontainers.image.created="${FARGLOW_CREATED}" \
      org.opencontainers.image.source="https://github.com/ennissh/farglow" \
      org.opencontainers.image.vendor="Citus Technologies, LLC" \
      org.opencontainers.image.licenses="BUSL-1.1"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    FARGLOW_BUILD=${FARGLOW_BUILD}

COPY containers/__NAME__/requirements.txt /tmp/requirements.txt
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi \
    && pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt \
    && python -m pip uninstall -y pip

RUN groupadd -g 1000 farglow \
    && useradd -u 1000 -g farglow -M -d /app -s /usr/sbin/nologin farglow

WORKDIR /app
COPY VERSION /app/VERSION
COPY migrations /app/migrations
COPY farglow /app/farglow
COPY containers/__NAME__/healthcheck.py /usr/local/bin/healthcheck.py

USER farglow
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "/usr/local/bin/healthcheck.py"]
CMD ["python", "-m", "farglow.__MODULE__"]
