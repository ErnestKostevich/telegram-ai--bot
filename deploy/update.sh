#!/usr/bin/env bash
# Pull latest code, install any new Python deps, restart the bot.
# Run as root (or via sudo). Idempotent — safe to call from GitHub Actions.

set -euo pipefail

APP_USER="disco-bot"
APP_DIR="/opt/disco-ai-bot"
SERVICE_NAME="disco-ai-bot"
REPO_BRANCH="main"

log()  { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\n\033[1;33m!!  %s\033[0m\n" "$*" >&2; }

if [[ "$EUID" -ne 0 ]]; then
    echo "Run with sudo." >&2
    exit 1
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
    echo "No bot install at $APP_DIR — run deploy/install.sh first." >&2
    exit 1
fi

cd "$APP_DIR"

# Warn (don't block) if anyone left local edits — `git reset --hard` will
# revert tracked-file changes silently. Untracked files survive reset, but
# we surface them too so the operator knows what's drifting.
DIRTY="$(sudo -u "$APP_USER" git status --porcelain 2>/dev/null || true)"
if [[ -n "$DIRTY" ]]; then
    warn "Local changes detected — git reset --hard will revert tracked files."
    warn "$DIRTY"
fi

log "Fetching latest from origin/$REPO_BRANCH"
sudo -u "$APP_USER" git fetch origin "$REPO_BRANCH"

PREV_COMMIT="$(sudo -u "$APP_USER" git rev-parse HEAD)"
sudo -u "$APP_USER" git reset --hard "origin/$REPO_BRANCH"
NEW_COMMIT="$(sudo -u "$APP_USER" git rev-parse HEAD)"

if [[ "$PREV_COMMIT" == "$NEW_COMMIT" ]]; then
    log "Already at $NEW_COMMIT — restarting anyway to pick up env / unit changes"
else
    log "Updated $PREV_COMMIT → $NEW_COMMIT"
fi

log "Refreshing Python deps"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt" --quiet

log "Restarting $SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# Give it 8s to crash on a broken release before we declare success — earlier
# 6s sometimes reported 'active' for a service that died right after.
sleep 8
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    warn "Service failed after deploy — rolling back to $PREV_COMMIT"
    sudo -u "$APP_USER" git reset --hard "$PREV_COMMIT"
    # --force-reinstall so removed-then-rolled-back deps are restored, not
    # left as silent ImportErrors at the next start.
    sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --force-reinstall -r "$APP_DIR/requirements.txt" --quiet
    systemctl restart "$SERVICE_NAME"
    journalctl -u "$SERVICE_NAME" -n 50 --no-pager
    exit 1
fi

log "Deploy ok — service is active on $NEW_COMMIT"
