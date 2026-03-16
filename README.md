# Work Report Hub

A small Flask app for collecting work reports from Codex agents and viewing them in one hosted dashboard.

## Features

- Push reports from any device or repo through a simple API.
- Protect API access with one shared `APP_API_KEY`.
- Use the same key to unlock the web dashboard in your browser.
- Require an explicit database connection string so the app never silently falls back to ephemeral local storage.
- Browse reports by project, repo, date, and title.

## Data model

Each report stores:

- `project_name`
- `repo_name`
- `title`
- `detail`
- `report_date`
- `source` (optional)

## Local run

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Then open `http://localhost:5000`.

## Environment variables

- `APP_API_KEY`: required for API writes and dashboard login
- `SECRET_KEY`: required for Flask session security
- `DATABASE_URL`: required, and should point to Railway PostgreSQL in production
- `PORT`: optional, Railway sets this automatically

## Railway deploy

1. Create a new Railway project from this repo.
2. Add a PostgreSQL service.
3. Set `APP_API_KEY`.
4. Set `SECRET_KEY`.
5. Set `DATABASE_URL` to Railway's PostgreSQL connection string.
6. Deploy. Railway will run the `web: gunicorn app:app` command from the `Procfile`.

The app auto-creates its table on startup.

## API

### Health check

```bash
curl https://your-app.up.railway.app/health
```

The health response now verifies both auth configuration and active database connectivity.

### Create report

```bash
curl -X POST https://your-app.up.railway.app/api/reports \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "project_name": "client-workspace",
    "repo_name": "github.com/your/repo",
    "title": "Delivered report syncing app",
    "detail": "Built the dashboard, API, and Railway deployment setup.",
    "report_date": "2026-03-12",
    "source": "codex"
  }'
```

### List reports

```bash
curl https://your-app.up.railway.app/api/reports \
  -H "X-API-Key: YOUR_API_KEY"
```

## Agent helper script

You can also push reports with the bundled helper:

```bash
python scripts/push_report.py \
  --app-url https://your-app.up.railway.app \
  --api-key YOUR_API_KEY \
  --project-name marketing-site \
  --repo-name Zhihong0321/marketing-site \
  --title "Shipped home page refresh" \
  --detail-file work-report-mar-12-2026-marketing-site.md \
  --report-date 2026-03-12
```

## Suggested Codex payload

Use this JSON shape from your agents:

```json
{
  "project_name": "marketing-site",
  "repo_name": "Zhihong0321/marketing-site",
  "title": "Fixed deploy blocker",
  "detail": "- Repaired environment loading\n- Verified production build\n- Updated docs for the team",
  "report_date": "2026-03-12",
  "source": "codex"
}
```
