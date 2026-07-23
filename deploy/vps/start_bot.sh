#!/bin/bash
# NOT wired into cron yet -- staged for cutover from the local Mac instance.
cd /opt/openclaw
mkdir -p logs
nohup .venv/bin/python3 main.py >> logs/bot_nohup.log 2>&1 &
disown
