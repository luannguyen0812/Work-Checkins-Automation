#!/bin/bash
if ! pgrep -f 'gunicorn.*wsgi:app' > /dev/null; then
  /opt/openclaw/deploy/vps/start_dashboard.sh
fi
