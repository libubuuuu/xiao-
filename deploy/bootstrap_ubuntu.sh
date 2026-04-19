#!/usr/bin/env bash

set -euo pipefail

log() {
    printf '\n==> %s\n' "$*"
}

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

quote_env() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    printf '"%s"' "$value"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

APP_SERVICE_NAME="${APP_SERVICE_NAME:-social-content-platform}"
APP_DOMAIN="${APP_DOMAIN:-app.example.com}"
APP_USER="${APP_USER:-socialapp}"
APP_GROUP="${APP_GROUP:-$APP_USER}"
APP_PORT="${APP_PORT:-8000}"
APP_ENV="${APP_ENV:-production}"
OWNER_ACCESS_TOKEN="${OWNER_ACCESS_TOKEN:-replace-me}"
REPO_BRANCH="${REPO_BRANCH:-main}"
ENV_FILE="/etc/${APP_SERVICE_NAME}.env"
SYSTEMD_UNIT="/etc/systemd/system/${APP_SERVICE_NAME}.service"
NGINX_SITE="/etc/nginx/sites-available/${APP_SERVICE_NAME}.conf"
APP_DB_PATH="${APP_DB_PATH:-$APP_DIR/backend/data/social_content.sqlite3}"

if [[ "$APP_DOMAIN" == "app.example.com" ]]; then
    die "Set APP_DOMAIN to your real subdomain before running this script."
fi

if [[ "$OWNER_ACCESS_TOKEN" == "replace-me" ]]; then
    die "Set OWNER_ACCESS_TOKEN to a strong secret before running this script."
fi

if [[ ! -d "$APP_DIR/.git" ]]; then
    die "Run this script from the repository root after cloning the project."
fi

log "Installing system packages"
sudo apt update
sudo apt install -y curl ca-certificates gnupg git nginx python3 python3-venv python3-pip ffmpeg

if ! command -v node >/dev/null 2>&1 || [[ "$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0)" -lt 18 ]]; then
    log "Installing Node.js 20 LTS"
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
fi

command -v npm >/dev/null 2>&1 || die "npm is required but was not installed."

log "Creating service account"
if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
    sudo groupadd --system "$APP_GROUP"
fi

if ! id -u "$APP_USER" >/dev/null 2>&1; then
    sudo useradd --system --create-home --shell /usr/sbin/nologin --gid "$APP_GROUP" "$APP_USER"
fi

log "Updating source code"
git -C "$APP_DIR" fetch origin "$REPO_BRANCH"
git -C "$APP_DIR" checkout "$REPO_BRANCH"
git -C "$APP_DIR" pull --ff-only origin "$REPO_BRANCH"

log "Building frontend"
cd "$APP_DIR/frontend"
if [[ -f package-lock.json ]]; then
    npm ci
else
    npm install
fi
npm run build

log "Installing backend dependencies"
cd "$APP_DIR/backend"
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt

log "Running backend smoke tests"
cd "$APP_DIR"
python3 -m unittest backend.tests.test_enterprise

log "Writing runtime environment"
sudo mkdir -p "$(dirname "$ENV_FILE")"
sudo tee "$ENV_FILE" >/dev/null <<EOF
APP_ENV=$(quote_env "$APP_ENV")
HOST=$(quote_env "127.0.0.1")
PORT=$(quote_env "$APP_PORT")
OWNER_ACCESS_TOKEN=$(quote_env "$OWNER_ACCESS_TOKEN")
APP_DB_PATH=$(quote_env "$APP_DB_PATH")
CORS_ORIGINS=$(quote_env "http://$APP_DOMAIN,https://$APP_DOMAIN")
EOF
sudo chmod 0644 "$ENV_FILE"

log "Writing systemd unit"
sudo tee "$SYSTEMD_UNIT" >/dev/null <<EOF
[Unit]
Description=Social Content Platform Console
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=-$ENV_FILE
ExecStart=$APP_DIR/backend/venv/bin/python main.py
Restart=always
RestartSec=3
User=$APP_USER
Group=$APP_GROUP

[Install]
WantedBy=multi-user.target
EOF

log "Writing Nginx site"
sudo tee "$NGINX_SITE" >/dev/null <<EOF
server {
    listen 80;
    server_name $APP_DOMAIN;

    client_max_body_size 50m;

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
EOF

sudo ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/${APP_SERVICE_NAME}.conf"

log "Preparing database path and permissions"
sudo mkdir -p "$(dirname "$APP_DB_PATH")"
sudo mkdir -p "$APP_DIR/backend/data"
sudo mkdir -p "$APP_DIR/backend/app/artifacts"
sudo touch "$APP_DB_PATH"
sudo chown "$APP_USER:$APP_GROUP" "$(dirname "$APP_DB_PATH")"
sudo chown "$APP_USER:$APP_GROUP" "$APP_DB_PATH"
sudo chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/backend/data"
sudo chown -R "$APP_USER:$APP_GROUP" "$APP_DIR/backend/app/artifacts"

log "Enabling and restarting services"
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now "$APP_SERVICE_NAME"
sudo systemctl reload nginx

log "Waiting for health check"
for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$APP_PORT/api/health" >/dev/null; then
        break
    fi
    sleep 1
done
curl -fsS "http://127.0.0.1:$APP_PORT/api/health" >/dev/null

printf '\nDeployment complete.\n'
printf 'Public URL: http://%s\n' "$APP_DOMAIN"
printf 'Health endpoint: http://%s/api/health\n' "$APP_DOMAIN"
printf 'Service: %s\n' "$APP_SERVICE_NAME"
