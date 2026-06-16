#!/usr/bin/env bash
# First-time setup for AI DISCO BOT on a fresh Ubuntu 24.04 VPS.
#
#   curl -fsSL https://raw.githubusercontent.com/ErnestKostevich/telegram-ai--bot/main/deploy/install.sh \
#       | sudo bash
#
# Or clone the repo and run: sudo bash deploy/install.sh
#
# Safe to re-run — operations are idempotent.

set -euo pipefail

APP_USER="disco-bot"
APP_DIR="/opt/disco-ai-bot"
ENV_DIR="/etc/disco-ai-bot"
ENV_FILE="$ENV_DIR/disco-ai-bot.env"
SERVICE_NAME="disco-ai-bot"
REPO_URL="https://github.com/ErnestKostevich/telegram-ai--bot.git"
REPO_BRANCH="main"

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }

if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo (need to create users/services)." >&2
    exit 1
fi

log "Updating apt + installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends \
    git python3 python3-venv python3-pip ca-certificates curl

log "Ensuring app user '$APP_USER' exists"
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi

log "Preparing $APP_DIR"
mkdir -p "$APP_DIR"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
    log "Cloning repository"
    sudo -u "$APP_USER" git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
else
    log "Repository already present — pulling latest"
    sudo -u "$APP_USER" -E git -C "$APP_DIR" fetch origin "$REPO_BRANCH"
    sudo -u "$APP_USER" -E git -C "$APP_DIR" reset --hard "origin/$REPO_BRANCH"
fi

log "Creating Python virtualenv"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

log "Setting up env directory $ENV_DIR"
mkdir -p "$ENV_DIR"
chmod 0750 "$ENV_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    install -m 0600 -o root -g root "$APP_DIR/deploy/disco-ai-bot.env.example" "$ENV_FILE"
    log "Created $ENV_FILE from the example. EDIT IT NOW to set real secrets:"
    log "    sudo nano $ENV_FILE"
else
    log "Existing env file kept: $ENV_FILE (not overwriting)"
fi

log "Installing systemd unit"
install -m 0644 "$APP_DIR/deploy/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

log "Starting service"
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl status --no-pager "$SERVICE_NAME" || true

cat <<EOF

================================================================
✅ Install complete.

Next steps:
  1. Fill in $ENV_FILE with your real secrets:
       sudo nano $ENV_FILE
     Then restart:
       sudo systemctl restart $SERVICE_NAME

  2. (Optional) configure nginx + TLS for Mini App and crypto webhook:
       sudo apt install -y nginx certbot python3-certbot-nginx
       sudo cp $APP_DIR/deploy/nginx-disco-ai-bot.conf /etc/nginx/sites-available/$SERVICE_NAME.conf
       sudo nano /etc/nginx/sites-available/$SERVICE_NAME.conf   # set your real domain
       sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME.conf /etc/nginx/sites-enabled/
       sudo nginx -t && sudo systemctl reload nginx
       sudo certbot --nginx -d disco.example.com

  3. (Optional) follow logs live:
       sudo journalctl -u $SERVICE_NAME -f
================================================================
EOF
