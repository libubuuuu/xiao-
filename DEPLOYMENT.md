# Deployment Guide

## System Requirements

### Minimum
- CPU: 2 cores
- RAM: 4 GB
- Storage: 1 GB for the demo app and dependencies
- OS: Windows 10+, macOS 10.15+, Ubuntu 20.04+

### Recommended
- CPU: 4+ cores
- RAM: 8 GB+
- Storage: 5 GB+

## Local Development

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The website and API share the same origin at `http://localhost:8000`.
Open the UI at `/` and the API summary at `/api`.

### Frontend

```bash
cd frontend
npm install
npm start
```

The UI runs on `http://localhost:3000`.

## Environment Variables

- `OWNER_ACCESS_TOKEN`: unlocks the owner-only publishing area. Default: `owner-demo-token`
- `REACT_APP_API_URL`: overrides the frontend API base URL
- `HOST`: backend bind address. Default: `0.0.0.0`
- `PORT`: backend port. Default: `8000`
- `APP_DB_PATH`: SQLite database path. Default: `backend/data/social_content.sqlite3`
- `APP_ENV`: runtime environment label. Default: `development`
- `APP_VERSION`: service version string. Default: `0.2.0`
- `CORS_ORIGINS`: comma-separated allowed origins for browser requests

## Production Notes

- Build the frontend with `npm run build` before deploying.
- Run the backend as a process service with `python main.py`; it serves the built UI and API from the same origin when `frontend/build` is present.
- The backend persists data in SQLite by default. Point `APP_DB_PATH` at a durable path if you move the project.
- If you split the frontend and API onto different hosts, set `REACT_APP_API_URL` to the API origin before building the frontend.
- If you run two projects on one server, give each one a different `PORT` and its own `systemd` unit or container.
- Use official or authorized platform integrations only.
- Use `/api/health` for uptime and storage checks.

## Operational Checklist

1. Set a strong owner token before production use.
2. Back up the SQLite database regularly, or move to PostgreSQL when the data volume grows.
3. Connect real publishing APIs only through approved integrations.
4. Add monitoring and audit logging before opening the system to other users.

## Deployment Templates

- Systemd unit: [`deploy/systemd/social-content-platform.service`](D:/Documents/New project/deploy/systemd/social-content-platform.service)
- Nginx site block: [`deploy/nginx/social-content-platform.conf`](D:/Documents/New project/deploy/nginx/social-content-platform.conf)
- Server notes: [`deploy/README.md`](D:/Documents/New project/deploy/README.md)
