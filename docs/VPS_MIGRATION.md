# 🖥 Migrate AI DISCO BOT from Fly.io → Ubuntu VPS

> Target: Ubuntu 24.04 VPS (e.g. `178.215.236.201`) where you already host 3 other bots.

The bot will run as a **systemd service** (auto-restart on failure, journald logs), inside its own venv at `/opt/disco-ai-bot/`, as a dedicated user `disco-bot`. Optional **nginx + Let's Encrypt** proxy is provided for the Mini App and NOWPayments webhook.

---

## TL;DR (one-time install)

SSH to the VPS as root or a sudoer, then:

```bash
curl -fsSL https://raw.githubusercontent.com/ErnestKostevich/telegram-ai--bot/main/deploy/install.sh | sudo bash
sudo nano /etc/disco-ai-bot/disco-ai-bot.env       # fill in secrets
sudo systemctl restart disco-ai-bot
sudo journalctl -u disco-ai-bot -f                 # follow logs
```

That's it for a polling-only deploy. NOWPayments and the Mini App need a domain + nginx + TLS (see below).

---

## What the installer does

1. Installs `git python3 python3-venv python3-pip ca-certificates curl`
2. Creates the `disco-bot` system user (no shell, no home login)
3. Clones the repo to `/opt/disco-ai-bot` owned by `disco-bot`
4. Creates `/opt/disco-ai-bot/.venv` and installs `requirements.txt`
5. Copies `disco-ai-bot.env.example` → `/etc/disco-ai-bot/disco-ai-bot.env` (mode 0600)
6. Installs the systemd unit at `/etc/systemd/system/disco-ai-bot.service`
7. Enables and starts the service

The script is idempotent — safe to re-run after edits.

---

## Coexistence with the other 3 bots

Each bot should have:

| Resource | This bot uses | Your other bots probably use |
|---|---|---|
| Service name | `disco-ai-bot.service` | `bot1.service`, `bot2.service`, … |
| Code dir | `/opt/disco-ai-bot/` | `/opt/bot1/`, … |
| User | `disco-bot` | `bot1`, … (or one shared user) |
| Env file | `/etc/disco-ai-bot/disco-ai-bot.env` | `/etc/bot1/bot1.env`, … |
| Internal HTTP port | `WEBHOOK_PORT=8081` (configurable) | If 8080 is taken — pick something free |

**Port collision check.** Before starting:

```bash
sudo ss -tlnp | grep -E ':808[0-9]'
```

If you see `8080` already in use, edit `/etc/disco-ai-bot/disco-ai-bot.env` and bump `WEBHOOK_PORT` to a free one (8081 / 8082 / 8083). The nginx vhost example reverse-proxies to 8081 — change it to match if you pick something else.

---

## Step 1 — Get the bot polling on the VPS

### 1.1 Prerequisites

- Ubuntu 24.04 (works on 22.04 too)
- A non-root user with `sudo`, OR root access
- The bot's Telegram `BOT_TOKEN`
- Your existing `GITHUB_TOKEN`/`GITHUB_REPO` for the JSON storage
- Your `CREATOR_ID` (your Telegram user id)

### 1.2 SSH in

```bash
ssh user@178.215.236.201
```

### 1.3 Stop the bot on Fly first (critical)

Telegram only lets ONE process call `getUpdates` per token at a time. Run **before** starting the VPS instance:

```bash
flyctl scale count 0 -a telegram-ai--bot          # from your local machine
```

Or in the Fly dashboard: app → Machines → stop the running machine.

Wait ~30 sec for Telegram to release the lock.

### 1.4 Run the installer on the VPS

```bash
curl -fsSL https://raw.githubusercontent.com/ErnestKostevich/telegram-ai--bot/main/deploy/install.sh | sudo bash
```

It will print where the env file lives and how to edit it.

### 1.5 Fill in secrets

```bash
sudo nano /etc/disco-ai-bot/disco-ai-bot.env
```

Set at minimum:

```
BOT_TOKEN=12345678:AAA...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=ErnestKostevich/telegram-ai-bot-db
GITHUB_FILE_PATH=bot_data.json
CREATOR_ID=123456789
WEBHOOK_PORT=8081
```

The monetization vars (`NOWPAYMENTS_*`, `PUBLIC_BASE_URL`) can stay empty for now — without them, `/buycrypto` shows the polite "temporarily off" message and Telegram Stars (`/buy`) still works.

Save & exit (`Ctrl-O`, `Enter`, `Ctrl-X`).

### 1.6 Restart and check

```bash
sudo systemctl restart disco-ai-bot
sudo systemctl status --no-pager disco-ai-bot
sudo journalctl -u disco-ai-bot -n 50 --no-pager
```

You should see `Bot is polling…` and `HTTP server listening on 0.0.0.0:8081`.

### 1.7 Smoke-test in Telegram

Open the bot and type `/start`. You should get the welcome card in English (or your client's language) with the v3.3 number.

### 1.8 Delete the Fly app (when ready)

After a few hours of stable VPS uptime, you can remove Fly entirely:

```bash
flyctl apps destroy telegram-ai--bot
```

---

## Step 2 — Enable auto-deploy from GitHub

So every `git push origin main` redeploys the VPS automatically.

### 2.1 Create an SSH key just for deploys

On your local machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-disco-ai-bot" -f ~/.ssh/disco_ai_bot_deploy -N ""
```

Don't reuse a personal key.

### 2.2 Authorise it on the VPS

Copy the public key:

```bash
cat ~/.ssh/disco_ai_bot_deploy.pub
```

On the VPS, append it to the deploy user's authorised keys:

```bash
# As the SSH user you'll use for deploys (e.g. root or a sudoer):
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'PASTE_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 2.3 Allow that user to run `update.sh` without a sudo password

`update.sh` needs root. To let GitHub Actions invoke it non-interactively:

```bash
sudo visudo -f /etc/sudoers.d/disco-ai-bot
```

Paste (replace `deployuser` with the actual SSH user):

```
deployuser ALL=(root) NOPASSWD: /opt/disco-ai-bot/deploy/update.sh
```

Save. Test:

```bash
sudo -n /opt/disco-ai-bot/deploy/update.sh
```

If it runs without asking for a password — good.

### 2.4 Capture the VPS SSH host fingerprint

On the VPS, run:

```bash
ssh-keyscan -t ed25519 localhost 2>/dev/null | ssh-keygen -lf - -E sha256
```

It prints a line like:

```
256 SHA256:abc123def456...   localhost (ED25519)
```

Copy the `SHA256:abc123...` part — that's the fingerprint. The workflow uses it to verify the host before any command runs, blocking MitM in the runner→VPS path.

### 2.5 Add GitHub repo secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Name | Value |
|---|---|
| `VPS_HOST` | `178.215.236.201` |
| `VPS_USER` | The SSH user (e.g. `deployuser` — **prefer over root**) |
| `VPS_SSH_KEY` | Contents of `~/.ssh/disco_ai_bot_deploy` (the **private** key, full PEM) |
| `VPS_HOST_FINGERPRINT` | The `SHA256:…` from step 2.4 |
| `VPS_SSH_PORT` | Only if your SSH listens somewhere other than 22 |

### 2.5 Disable the old Fly workflow

Either delete `.github/workflows/fly-deploy.yml` or rename it to `fly-deploy.yml.disabled` so it doesn't fight the new workflow.

```bash
git mv .github/workflows/fly-deploy.yml .github/workflows/fly-deploy.yml.disabled
```

### 2.6 Trigger a deploy

```bash
git commit --allow-empty -m "test: trigger vps deploy"
git push origin main
```

Watch the run in the **Actions** tab. On success, the VPS will have been pulled and restarted, and `journalctl -u disco-ai-bot` will show a fresh "Bot is ready!" line.

---

## Step 3 — nginx + TLS (only needed for NOWPayments & Mini App)

The bot's HTTP server (port `WEBHOOK_PORT`) needs to be reachable from the public internet over HTTPS for two reasons:

1. **NOWPayments IPN** posts to `https://<your-domain>/webhook/nowpayments`
2. **Telegram Mini App** loads `https://<your-domain>/webapp` inside Telegram

If you don't use crypto payments or the Mini App, you can skip this entirely — Stars (`/buy`) and everything else work purely via polling.

### 3.1 Point a domain at the VPS

Buy a domain (or use a free subdomain), then create an `A` record:

```
disco.example.com.  IN  A  178.215.236.201
```

Wait for DNS to propagate (`dig disco.example.com` should return your IP).

### 3.2 Install nginx + certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 3.3 Drop in the vhost

```bash
sudo cp /opt/disco-ai-bot/deploy/nginx-disco-ai-bot.conf /etc/nginx/sites-available/disco-ai-bot.conf
sudo nano /etc/nginx/sites-available/disco-ai-bot.conf     # replace disco.example.com with your real domain
sudo ln -s /etc/nginx/sites-available/disco-ai-bot.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3.4 Get a TLS cert

```bash
sudo certbot --nginx -d disco.example.com
```

Certbot will edit the vhost in place, add the SSL block, and set up auto-renewal via a systemd timer.

### 3.5 Tell the bot its public URL

```bash
sudo nano /etc/disco-ai-bot/disco-ai-bot.env
```

Set:

```
PUBLIC_BASE_URL=https://disco.example.com
```

Restart:

```bash
sudo systemctl restart disco-ai-bot
```

### 3.6 Update NOWPayments webhook

In NOWPayments dashboard → Settings → Instant Payment Notifications, set:

```
Webhook URL: https://disco.example.com/webhook/nowpayments
```

Save. Optionally add 3 recurring notifications at 30-minute intervals as backup.

### 3.7 Update Mini App URL in @BotFather

In Telegram → **@BotFather** → `/mybots` → `@AI_DISCO_BOT` → **Bot Settings → Menu Button → Edit menu button URL**:

```
https://disco.example.com/webapp
```

---

## Operations cheat sheet

```bash
# Logs
sudo journalctl -u disco-ai-bot -f                    # live tail
sudo journalctl -u disco-ai-bot -n 200 --no-pager     # last 200 lines

# Service
sudo systemctl restart disco-ai-bot
sudo systemctl stop disco-ai-bot
sudo systemctl status disco-ai-bot

# Manual deploy without GitHub Actions
sudo /opt/disco-ai-bot/deploy/update.sh

# Edit secrets
sudo nano /etc/disco-ai-bot/disco-ai-bot.env
sudo systemctl restart disco-ai-bot                   # apply

# Health check
curl -s http://127.0.0.1:8081/healthz                 # from the VPS
curl -s https://disco.example.com/healthz             # from the internet (after nginx+TLS)

# Disk / memory
df -h /opt/disco-ai-bot
sudo systemctl show disco-ai-bot --property=MemoryCurrent

# Roll back manually
cd /opt/disco-ai-bot
sudo -u disco-bot git log --oneline -5
sudo -u disco-bot git reset --hard <good-commit>
sudo systemctl restart disco-ai-bot
```

---

## Firewall reminder

If you use `ufw`:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'   # only if you set up nginx
sudo ufw enable
sudo ufw status
```

The bot's `WEBHOOK_PORT` (8081) does **not** need to be opened externally — only nginx on 80/443 does. nginx talks to the bot over localhost.

---

## Troubleshooting

### `systemctl status disco-ai-bot` says "active (failed)"

```bash
sudo journalctl -u disco-ai-bot -n 100 --no-pager
```

Look for the first traceback. Common culprits:
- `KeyError: 'BOT_TOKEN'` → env file missing a required var
- `aiohttp ... Connection refused` → outgoing network blocked
- `409 Conflict ... terminated by other getUpdates request` → Fly is still polling. Stop Fly (`flyctl scale count 0 -a telegram-ai--bot`) and wait 30s.

### Bot starts but `/start` doesn't reply

Probably wrong `BOT_TOKEN`. Verify with:

```bash
sudo grep BOT_TOKEN /etc/disco-ai-bot/disco-ai-bot.env
```

### `/buycrypto` shows "temporarily off"

`NOWPAYMENTS_API_KEY` is empty. Fill in the env, restart.

### Mini App "Cannot read initData" / blank page

`PUBLIC_BASE_URL` is empty OR nginx isn't routing `/webapp`. Test with:

```bash
curl -i https://disco.example.com/webapp
```

Expect HTTP 200 with HTML body.

### GitHub Actions deploy fails with `Permission denied (publickey)`

The SSH key in `VPS_SSH_KEY` doesn't match what's in `~/.ssh/authorized_keys` on the VPS. Verify the **full** PEM body (including `-----BEGIN OPENSSH PRIVATE KEY-----`) is in the secret.

### `update.sh` rolls back automatically

Means the new release crashed within 6 seconds. Check `journalctl -u disco-ai-bot -n 50` for the traceback, fix in code, push again.
