#!/bin/bash
cd /opt/openclaw
mkdir -p logs
nohup .venv/bin/gunicorn --workers 1 --bind 127.0.0.1:5050 --timeout 60 \
  --access-logfile logs/gunicorn-access.log \
  --error-logfile logs/gunicorn-error.log \
  wsgi:app >> logs/dashboard_nohup.log 2>&1 &
disown
