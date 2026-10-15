#!/usr/bin/env bash
set -e

# The daily batch is triggered externally by the Coolify scheduler
# (POST /run on the health server), so no cron runs inside this container.
exec python3 health_server.py
