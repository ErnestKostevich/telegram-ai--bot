#!/usr/bin/env bash
# Pull latest code, install any new Python deps, restart the bot.
# Run as root (or via sudo). Idempotent — safe to call from GitHub Actions.

set -euo pipefail

APP_USER="disco-bot"
APP_DIR="/opt/disco-ai-bot"
SERVICE_NAME="disco-ai-bot"
REPO_BRANCH="main"

log() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }

if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

cd "$APP_DIR"

log "Fetching latest from origin/$REPO_BRANCH"
sudo -u "$APP_USER" git fetch origin "$REPO_BRANCH"

# Save the commit we were on, in case we need to roll back.
PREV_COMMIT="$(sudo -u "$APP_USER" git rev-parse HEAD)"

sudo -u "$APP_USER" git reset --hard "origin/$REPO_BRANCH"
NEW_COMMIT="$(sudo -u "$APP_USER" git rev-parse HEAD)"

log "Updated $PREV_COMMIT → $NEW_COMMIT"

log "Refreshing Python deps"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet

log "Restarting $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Give it 6s to crash on a broken release before we declare success.
sleep 6
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    log "⚠ Service failed after deploy — rolling back to $PREV_COMMIT"
    sudo -u "$APP_USER" git reset --hard "$PREV_COMMIT"
    sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet
    systemctl restart "$SERVICE_NAME"
    journalctl -u "$SERVICE_NAME" -n 50 --no-pager
    exit 1
fi

log "✅ Deploy ok — service is active on $NEW_COMMIT"
