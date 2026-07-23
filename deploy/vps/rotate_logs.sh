#!/bin/bash
# Weekly log maintenance for a sudo-free deployment (no logrotate installed,
# no /etc/logrotate.d access). Runs via cron, no admin privileges needed.
set -e
LOG_DIR=/opt/openclaw/logs
STAMP=$(date +%Y%m%d)
cd "$LOG_DIR"

# 1. Gunicorn access/error logs: gunicorn reopens log files on SIGUSR1,
#    so a plain mv is safe as long as we signal the master afterward.
GUNICORN_PID=$(pgrep -u luan -f 'gunicorn --workers 1 --bind 127.0.0.1:5050' | head -1)
for f in gunicorn-access.log gunicorn-error.log; do
  if [ -s "$f" ]; then
    mv "$f" "${f}.${STAMP}"
    gzip -f "${f}.${STAMP}"
  fi
done
if [ -n "$GUNICORN_PID" ]; then
  kill -USR1 "$GUNICORN_PID"
fi

# 2. nohup stdout/stderr redirects: these are raw shell redirection, not
#    something the app can reopen on signal, so a rename would leave the
#    running process writing to the old (now hidden) inode forever.
#    Copy-then-truncate-in-place instead -- the process keeps its same fd.
for f in bot_nohup.log dashboard_nohup.log; do
  if [ -s "$f" ]; then
    cp "$f" "${f}.${STAMP}"
    gzip -f "${f}.${STAMP}"
    : > "$f"
  fi
done

# 3. parse_schedules cron log: single short-lived writer per run, safe to
#    rotate directly between runs.
if [ -s parseschedules.log ]; then
  mv parseschedules.log "parseschedules.log.${STAMP}"
  gzip -f "parseschedules.log.${STAMP}"
fi

# 4. Delete rotated archives older than 60 days.
find "$LOG_DIR" -maxdepth 1 -name "*.log.*.gz" -mtime +60 -delete

# 5. Dated bot_YYYY-MM-DD.log files: the app opens one of these once at
#    process startup and keeps writing to it via a fixed file handle even
#    across midnight, so never delete whichever one is currently open --
#    check via /proc/<pid>/fd rather than trusting the filename/date alone.
BOT_PID=$(pgrep -u luan -f '.venv/bin/python3 main.py' | head -1)
OPEN_BOT_LOG=""
if [ -n "$BOT_PID" ] && [ -d "/proc/$BOT_PID/fd" ]; then
  OPEN_BOT_LOG=$(ls -la "/proc/$BOT_PID/fd" 2>/dev/null | grep -o 'bot_[0-9-]*\.log' | head -1)
fi
find "$LOG_DIR" -maxdepth 1 -name "bot_*.log" -mtime +60 -print | while read -r f; do
  base=$(basename "$f")
  if [ "$base" != "$OPEN_BOT_LOG" ]; then
    rm -f "$f"
  fi
done

echo "Log rotation completed at $(date)"
