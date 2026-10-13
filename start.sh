#!/usr/bin/env bash
set -e

# make sure the daily log exists
touch /var/log/video-worker.log

# start cron in the background and keep a health endpoint in the foreground
cron
exec python3 health_server.py
