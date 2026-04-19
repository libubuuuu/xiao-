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

