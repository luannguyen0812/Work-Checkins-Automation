#!/bin/bash
# Run once on the VPS as root or sudo user
# Ubuntu 22.04 LTS assumed
set -e

echo "=== 1. System packages ==="
apt update && apt upgrade -y
apt install -y git nginx python3.13 python3.13-venv certbot python3-certbot-nginx

echo "=== 2. App directory ==="
mkdir -p /opt/intern-checkin-bot
chown ubuntu:ubuntu /opt/intern-checkin-bot

echo "=== 3. Clone repo ==="
# Replace with your actual git remote once you push
# git clone https://github.com/YOUR_ORG/intern-checkin-bot.git /opt/intern-checkin-bot
echo "TODO: copy files to /opt/intern-checkin-bot (git clone or scp)"

echo "=== 4. Python venv ==="
cd /opt/intern-checkin-bot
python3.13 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "=== 5. .env file ==="
echo "TODO: copy your .env to /opt/intern-checkin-bot/.env"
echo "      scp .env ubuntu@YOUR_VPS_IP:/opt/intern-checkin-bot/.env"
echo "      scp /path/to/service-account.json ubuntu@YOUR_VPS_IP:/opt/intern-checkin-bot/service-account.json"
echo "      Then update GOOGLE_SERVICE_ACCOUNT_JSON in .env to /opt/intern-checkin-bot/service-account.json"

echo "=== 6. Logs directory ==="
mkdir -p /opt/intern-checkin-bot/logs
chown ubuntu:ubuntu /opt/intern-checkin-bot/logs

echo "=== 7. Systemd services ==="
cp /opt/intern-checkin-bot/deploy/intern-checkin-bot.service /etc/systemd/system/
cp /opt/intern-checkin-bot/deploy/intern-checkin-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable intern-checkin-bot intern-checkin-dashboard
systemctl start intern-checkin-bot intern-checkin-dashboard

echo "=== 8. Nginx ==="
cp /opt/intern-checkin-bot/deploy/nginx.conf /etc/nginx/sites-available/intern-checkin
ln -sf /etc/nginx/sites-available/intern-checkin /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== 9. SSL (optional — needs a real domain pointed at this VPS) ==="
echo "Run: certbot --nginx -d YOUR_DOMAIN"

echo ""
echo "=== Done! Check status with: ==="
echo "  systemctl status intern-checkin-bot"
echo "  systemctl status intern-checkin-dashboard"
echo "  journalctl -u intern-checkin-bot -f"
