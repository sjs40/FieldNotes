# Fieldnotes

Fieldnotes is a personal research journal and public-equity call tracker. It
keeps the original calm, information-dense UI while using a FastAPI API,
PostgreSQL-compatible persistence, and optional Supabase authentication.

## Run locally

### Easiest option

Double-click `Start Fieldnotes.bat` in Windows Explorer. It starts the local
server and opens the journal in your default browser.

Or, from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000), rather than opening
`index.html` directly.

Notes, drafts, tracked calls, and price refreshes are API-owned; browser local
storage is not used as a source of truth. The **Update stock prices** button
refreshes the signed-in user's open calls through the backend. Quote retrieval
uses yfinance with a Yahoo chart-API fallback, isolated in
`backend/app/market_data.py` for future provider replacement.

## Architecture

- `backend/app/parser.py` — deterministic parsing of note types, tags,
  tickers, calls, and pairs.
- `backend/app/models.py` — normalized notes, revisions, tags, ticker mentions,
  securities, prices, calls, legs, benchmarks, and events.
- `backend/app/journal.py` — transactional persistence and compatibility
  serialization for the existing UI.
- `backend/app/main.py` — authenticated REST endpoints for notes, calls,
  tickers, revisions, quote refresh, lifecycle events, and export.
- `refresh-prices.js` — UI adapter for the authenticated quote-refresh API.

SQLite is used for frictionless local development. Production uses managed
PostgreSQL (for example Supabase) and Supabase Auth.

## API overview

- `GET/POST /api/notes` — list or save a draft for the current user.
- `POST /api/notes/publish` — publish a note and atomically capture tracker
  entry prices.
- `GET /api/notes/search?q=…` and `GET /api/notes/{id}/revisions` — search and
  revision history.
- `GET /api/calls`, `GET /api/tickers`, `POST /api/calls/{id}/{event}` —
  normalized research and lifecycle data.
- `POST /api/market-data/refresh` — refresh open-call prices for the current
  user.

The legacy prototype importer remains available at
`POST /api/notes/import-legacy` (and as `backend/scripts/migrate_legacy_calls.py`)
for an intentional, reviewed migration. It is not used by the current UI.

## Production database and migrations

Set `ENVIRONMENT=production`, a managed PostgreSQL `DATABASE_URL` (for example
Supabase), `SUPABASE_URL`, and a publishable Supabase key. SQLite is
intentionally rejected in production.

Application startup never runs migrations. Run them explicitly in a trusted
environment; production requires an intentional confirmation:

```powershell
python -m backend.scripts.run_migrations
# production only: $env:FIELDNOTES_CONFIRM_MIGRATIONS='yes'
```

Inspect a revision with `alembic current`; rollback with `alembic downgrade -1`
after validating the migration is reversible. For previews, migrate the preview
database before its deployment. Production sequence: `alembic upgrade head`,
then `vercel deploy --prod`, then check `/api/health/ready`.

The Vercel entry point is `api/index.py`; `vercel.json` rewrites all requests
to that FastAPI application, which serves both the UI and `/api/*`. Do not
commit `.env`, database files, Supabase keys, or credentials.

## Checks

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
python -m unittest discover -s backend/tests -v
node --check app-modern.js
node --check refresh-prices.js
```

## IBKR portfolio foundation

Portfolio ingestion is read-only. Vercel cannot connect to TWS running on your
Windows machine: a local agent in `integrations/ibkr_sync_agent` pushes HTTPS
snapshots with a narrowly scoped token. No trading, orders, cancellations, or
transfers are implemented. Never commit IBKR or sync credentials.
