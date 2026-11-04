# farglow-uitest: the headless-browser UI suite (test only; never part of an install).
# Built from tests/ui/ by tests/ui/ui-test.sh. The official Playwright image, pinned by digest,
# carries Python, Playwright 1.64.1 and Chromium with its system libraries.
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble@sha256:330d401ae23c905896a0c26c66c36fc971b621519e7b11b435a8328d7bf6e031
WORKDIR /suite
COPY requirements.txt /tmp/requirements.txt
# Optional extra CA for a TLS-intercepting proxy (FARGLOW_BUILD_CA_FILE), as a BuildKit secret.
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi \
    && pip install --no-cache-dir --root-user-action=ignore --only-binary=:all: --break-system-packages -r /tmp/requirements.txt
COPY uitest.py budgets.json /suite/
USER pwuser
ENTRYPOINT ["python3", "/suite/uitest.py"]
