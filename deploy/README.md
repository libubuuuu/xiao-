# Server Deployment

This project is designed to run as a single backend process that serves:

- the API
- the built frontend
- the `/docs` endpoint

Use this layout on Ubuntu:

```text
/var/www/xiao/
  backend/
  frontend/
```

## Recommended Runtime

- `Nginx` on port `80` and `443`
- `systemd` for the backend process
- one backend port per project, controlled by `PORT`

## Subdomain Setup

If your main domain is already serving another site, point a subdomain to this project:

1. Create an `A` record for your subdomain, for example `app.example.com`.
2. Point it to the server IP, for example `43.134.71.189`.
3. Put the Nginx config in `deploy/nginx/social-content-platform.conf` on the server.
4. Replace `app.example.com` in that file with your real subdomain.
5. Reload Nginx after testing the config.

Example commands:

```bash
sudo cp /var/www/xiao/deploy/nginx/social-content-platform.conf /etc/nginx/sites-available/social-content-platform.conf
sudo ln -s /etc/nginx/sites-available/social-content-platform.conf /etc/nginx/sites-enabled/social-content-platform.conf
sudo nginx -t
sudo systemctl reload nginx
```

If you want HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d app.example.com
```

## First-Time Install

```bash
sudo apt update
sudo apt install -y git nginx python3 python3-venv python3-pip nodejs npm
```

## Build and Run

```bash
cd /var/www/xiao/frontend
npm install
npm run build

cd /var/www/xiao/backend
python3 -m venv venv
venv/bin/pip install -r requirements.txt
PORT=8000 OWNER_ACCESS_TOKEN=replace-me venv/bin/python main.py
```

## Multi-Project Notes

If you deploy a second project on the same server:

1. Copy the repo into a second directory.
2. Change the backend `PORT` for that project, for example `8001`.
3. Give it a separate `systemd` unit file.
4. Give it a separate `Nginx` server block or subdomain.
