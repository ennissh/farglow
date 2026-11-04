#!/bin/sh
# Pick the site template: TLS when a certificate is mounted at /etc/farglow/tls, else HTTP.
# (Let's Encrypt automation is an open item; see PLAN.md.)
set -eu
mkdir -p /tmp/farglow-templates
if [ -s /etc/farglow/tls/fullchain.pem ] && [ -s /etc/farglow/tls/privkey.pem ]; then
    cp /etc/farglow/nginx/tls.conf.template /tmp/farglow-templates/default.conf.template
    echo "farglow: TLS enabled (certificate found in /etc/farglow/tls)"
else
    cp /etc/farglow/nginx/http.conf.template /tmp/farglow-templates/default.conf.template
    echo "farglow: no certificate in /etc/farglow/tls - serving plain HTTP"
fi
