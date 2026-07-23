#!/bin/bash
if ! pgrep -f '.venv/bin/python3 main.py' > /dev/null; then
  /opt/openclaw/deploy/vps/start_bot.sh
fi
