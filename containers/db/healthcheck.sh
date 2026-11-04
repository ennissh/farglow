#!/bin/sh
# Ready means: accepting connections on TCP for the Farglow database (not just the socket,
# which answers during initdb's temporary server).
exec pg_isready -q -h 127.0.0.1 -U "${POSTGRES_USER:-farglow}" -d "${POSTGRES_DB:-farglow}"
