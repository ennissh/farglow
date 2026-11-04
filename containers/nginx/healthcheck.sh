#!/bin/sh
exec wget -q -T 4 -O /dev/null http://127.0.0.1:8080/nginx-health
