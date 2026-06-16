#!/usr/bin/env bash
# First-time setup for AI DISCO BOT on a fresh Ubuntu 24.04 VPS.
#
# One-liner:
#   curl -fsSL https://raw.githubusercontent.com/ErnestKostevich/telegram-ai--bot/main/deploy/install.sh \
#       | sudo bash
#
# Safe to re-run — operations are idempotent. The whole body lives inside
# main() so a truncated download (curl-pipe partial-execution risk) cannot
# execute partial logic — main() is only called at the end of the file.

set -euo pipefail

APP_USER="disco-bot"
APP_DIR="/opt/disco-ai-bot"
ENV_DIR="/etc/disco-ai-bot"
ENV_FILE="$ENV_DIR/disco-ai-bot.env"
SERVICE_NAME="disco-ai-bot"
REPO_URL="https://github.com/ErnestKostevich/telegram-ai--bot.git"
REPO_BRANCH="main"

log()  { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
warn() { printf "\n\033[1;33m!!  %s\033[0m\n" "$*" >&2; }

apt_safe() {
    # Wait up to 2 min for the dpkg lock — unattended-upgrades is common on Ubuntu 24.
    DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 "$@"
}

ensure_user() {
    if id "$APP_USER" >/dev/null 2>&1; then
        # Existing account — enforce hardened attributes even if a prior install
        # or an admin created it differently.
        local uid shell
        uid="$(getent passwd "$APP_USER" | awk -F: '{print $3}')"
        shell="$(getent passwd "$APP_USER" | awk -F: '{print $7}')"
        if [[ "$uid" -ge 1000 ]]; then
            warn "User $APP_USER has UID $uid (>=1000). Leaving as-is — manual review recommended."
        fi
        if [[ "$shell" != "/usr/sbin/nologin" && "$shell" != "/bin/false" ]]; then
            log "Tightening $APP_USER shell to /usr/sbin/nologin (was: $shell)"
            usermod --shell /usr/sbin/nologin "$APP_USER"
        fi
    else
        useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
    fi
}

ensure_clone() {
    # Refuse to clobber a non-empty directory that is NOT a git checkout — that
    # would silently destroy state from an aborted prior run or admin overlay.
    if [[ -d "$APP_DIR/.git" ]]; then
        log "Repository already present — pulling latest"
        sudo -u "$APP_USER" -E git -C "$APP_DIR" fetch origin "$REPO_BRANCH"
        sudo -u "$APP_USER" -E git -C "$APP_DIR" reset --hard "origin/$REPO_BRANCH"
        return
    fi
    if [[ -d "$APP_DIR" && -n "$(ls -A "$APP_DIR" 2>/dev/null || true)" ]]; then
        warn "$APP_DIR exists, is non-empty, and has no .git/ — refusing to overwrite."
        warn "Move or remove it first (sudo rm -rf $APP_DIR), then re-run install.sh."
        exit 1
    fi
    mkdir -p "$APP_DIR"
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"
    log "Cloning repository"
    sudo -u "$APP_USER" git clone --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
}

ensure_venv() {
    # Rebuild venv if the system python interpreter major.minor has drifted
    # from the venv's pinned interpreter — common after dist-upgrades.
    local sys_py venv_py
    sys_py="$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ -x "$APP_DIR/.venv/bin/python" ]]; then
        venv_py="$("$APP_DIR/.venv/bin/python" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo unknown)"
        if [[ "$venv_py" != "$sys_py" ]]; then
            warn "venv python ($venv_py) != system python ($sys_py) — rebuilding venv."
            rm -rf "$APP_DIR/.venv"
        fi
    fi
    if [[ ! -x "$APP_DIR/.venv/bin/python" ]]; then
        log "Creating Python virtualenv"
        sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
    fi
    sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
    sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
}

ensure_env_file() {
    mkdir -p "$ENV_DIR"
    chmod 0750 "$ENV_DIR"
    if [[ ! -f "$ENV_FILE" ]]; then
        install -m 0600 -o root -g root "$APP_DIR/deploy/disco-ai-bot.env.example" "$ENV_FILE"
        log "Created $ENV_FILE from the example. EDIT IT NOW to set real secrets:"
        log "    sudo nano $ENV_FILE"
    else
        log "Existing env file kept: $ENV_FILE (not overwriting)"
    fi
    # Re-assert mode/owner in case someone (incl. previous installs) drifted it.
    # 0600 root:root is intentional — systemd reads EnvironmentFile as PID 1
    # BEFORE dropping to User=disco-bot, so disco-bot must NOT own it.
    chmod 0600 "$ENV_FILE"
    chown root:root "$ENV_FILE"
}

main() {
    if [[ "$EUID" -ne 0 ]]; then
        echo "Run with sudo (need to create users/services)." >&2
        exit 1
    fi

    log "Updating apt + installing system packages"
    apt_safe update -y
    apt_safe install -y --no-install-recommends \
        git python3 python3-venv python3-pip ca-certificates curl

    log "Ensuring app user '$APP_USER' exists with hardened attributes"
    ensure_user

    log "Preparing $APP_DIR"
    ensure_clone
    chown -R "$APP_USER:$APP_USER" "$APP_DIR"

    log "Setting up virtualenv + Python deps"
    ensure_venv

    log "Setting up env directory $ENV_DIR"
    ensure_env_file

    log "Installing systemd unit"
    install -m 0644 "$APP_DIR/deploy/$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    # We do NOT auto-start here — env file is almost certainly empty on first
    # install, and crash-looping with InvalidToken would fill the journal.
    # The post-install banner tells the operator to edit the env file then
    # restart explicitly. Re-runs (env already configured) still restart cleanly.
    if [[ -s "$ENV_FILE" ]] && grep -q '^BOT_TOKEN=.\+' "$ENV_FILE"; then
        log "Env file looks populated — restarting service"
        systemctl restart "$SERVICE_NAME"
        sleep 4
        systemctl status --no-pager "$SERVICE_NAME" || true
    else
        warn "Env file is empty or missing BOT_TOKEN — NOT starting the service yet."
    fi

    cat <<EOF

================================================================
Install complete.

Next steps:
  1. Fill in $ENV_FILE with your real secrets:
       sudo nano $ENV_FILE
     Then start the service:
       sudo systemctl restart $SERVICE_NAME
       sudo journalctl -u $SERVICE_NAME -f

  2. (Optional) configure nginx + TLS for Mini App and crypto webhook.
     If nginx already runs on this VPS for other bots, see deploy/README
     in the repo — do NOT copy the vhost as-is, it claims default_server.

  3. (Optional) follow logs live:
       sudo journalctl -u $SERVICE_NAME -f
================================================================
EOF
}

# Only run main when the whole file has been parsed — protects against
# curl-pipe partial execution.
main "$@"
