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

## Production Notes

- Build the frontend with `npm run build` before deploying.
- Run the backend as a process service with `python main.py`; it serves the built UI and API from the same origin when `frontend/build` is present.
- If you split the frontend and API onto different hosts, set `REACT_APP_API_URL` to the API origin before building the frontend.
- Use official or authorized platform integrations only.

## Operational Checklist

1. Set a strong owner token before production use.
2. Replace the in-memory store with a persistent database if you need real retention.
3. Connect real publishing APIs only through approved integrations.
4. Add monitoring and audit logging before opening the system to other users.
