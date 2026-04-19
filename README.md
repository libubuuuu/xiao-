# Social Content Platform Console

Enterprise starter for a compliant social content operations platform.

## What It Covers

- Domestic and overseas platform selection
- Content radar with source attribution and trend analysis
- Cart-based content selection and remixing
- Image canvas for similarity generation
- Owner-only publishing flow to draft boxes or queues
- AI comment suggestion workflow with human review

## Compliance Boundary

This project intentionally does not include:

- IP rotation or IP isolation
- Anti-detection or bypassing platform risk controls
- Unauthorized multi-account abuse
- Automated spam or covert mass-commenting

Publishing and account access should use official APIs or other authorized integrations.

## Tech Stack

- Frontend: React
- Backend: Python standard-library HTTP server with a Starlette-compatible app layer
- Data: SQLite-backed repository with on-disk persistence, ready to swap to PostgreSQL later

## Project Layout

```text
backend/
  main.py
  app/
    config.py
    repository.py
    models.py
    server.py
    store.py
  tests/
    test_enterprise.py
frontend/
  src/
    App.js
    App.css
    config.js
```

## Run Locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The UI and API will run on the same origin at `http://localhost:8000`.
Open the website at `/` and the API summary at `/api`.
The health endpoint is available at `/api/health`.

### Frontend

```bash
cd frontend
npm install
npm start
```

The app will run at `http://localhost:3000`.

## Owner Console

The publishing center is locked by default.

Set the token to unlock:

```text
owner-demo-token
```

You can replace it with your own environment variable:

```bash
set OWNER_ACCESS_TOKEN=your-secret-token
```

## Notes

- The backend uses mock data so the console works without external services.
- The backend persists workspace data in `backend/data/social_content.sqlite3`.
- You can later replace the mock data layer with real platform integrations.
- The current repo is now aligned to the new social content product direction, not the old sync analyzer demo.
- The backend exposes the website at `/`, the API summary at `/api`, and the docs note at `/docs`.
- The backend health and storage status are exposed at `/api/health`.
- Image and video artifact generation requires `ffmpeg` to be installed and available on `PATH`.
- Deployment templates live under [`deploy/README.md`](D:/Documents/New project/deploy/README.md).
- For Ubuntu servers, the fastest path is [`deploy/bootstrap_ubuntu.sh`](D:/Documents/New project/deploy/bootstrap_ubuntu.sh).
