# Fieldnotes

Personal notes and investment-journal V1. The current calm, information-dense UI is preserved, but notes, call data, price refreshes, and future integrations now have a FastAPI boundary.

## Run locally

### Easiest option

Double-click [Start Fieldnotes.bat](<Start Fieldnotes.bat>) in Windows Explorer. It starts the local server and opens the journal in your default browser.

1. Install backend dependencies:

   ```powershell
   python -m pip install -r backend\requirements.txt
   ```

2. Start the application from the repository root:

   ```powershell
   python -m uvicorn backend.app.main:app --reload --port 8000
   ```

3. Open [http://localhost:8000](http://localhost:8000), rather than opening `index.html` directly.

The first page load syncs the notes already stored by the previous browser-only version into `fieldnotes.db`. Thereafter, UI saves are mirrored to the API. The **Update stock prices** button calls the backend, which uses the `YFinanceMarketDataProvider`; provider code is isolated in `backend/app/market_data.py` for future replacement.

## Architecture

- `backend/app/parser.py` — deterministic parsing of note types, tags, tickers, calls, and pairs.
- `backend/app/market_data.py` — provider boundary; only this module knows about yfinance.
- `backend/app/models.py` — normalized note, tag, security, price-cache, and call-event tables.
- `backend/app/main.py` — REST endpoints for notes, parse, generic capture, price refresh, lifecycle events, and export.
- `api-bridge.js` / `refresh-prices.js` — adapters preserving the existing UI while using the API.

SQLite is used for frictionless single-user local development. `docker-compose.yml` provides PostgreSQL and Redis for the next stage: Alembic migrations, worker-based quote refresh, ingestion, and AI enrichment.

## Checks

```powershell
python -m backend.tests.smoke_test
node --check app.js
```
