# Sprint 1 reasoning ledger implementation report

## Delivered data model

- Universal note relationships now retain legacy `update_of` rows and accept `updates`, `supports`, `contradicts`, `answers`, `derived_from`, `supersedes`, `related`, `challenge_to`, and `converts_to`.
- Relationships carry an optional user, explanation, workflow marker, and a duplicate-prevention constraint.
- Normalized `thinking_updates`, assumptions plus immutable assumption events, evidence plus evidence-to-assumption/thesis/forecast/question links, research questions plus events, forecasts plus events, and saved views were added.
- Forecast resolution preserves the forecast and records resolution, classified outcome, and deterministic point-forecast error.

## Migration

- `c3d4e5f6a7b8_reasoning_ledger` extends `note_relationships`, backfills relationship owners from source notes, and creates the ledger tables.
- `d4e5f6a7b8c9_complete_reasoning_workflows` adds the remaining event/link/view tables and an explicit no-self-relationship check. Both use SQLite-compatible batch alteration and downgrade paths.

## API workflows

- `POST /api/notes/{id}/follow-ups` creates a published note, relationship, optional thinking update, and pending questions in one transaction.
- `GET /api/notes/{id}/relationships` returns user-scoped forward and backlinks.
- `POST/GET /api/assumptions`, `POST /api/evidence`, `POST/GET /api/questions`, and `POST /api/forecasts` provide normalized capture and queue workflows.
- `POST /api/forecasts/{id}/resolve` requires an explicit resolution outcome.
- Conversion, thesis challenge, assumption/question/forecast histories, saved views, and deterministic daily/weekly review summaries are available through resource APIs.
- Ticker detail responses and timeline now expose assumptions, active evidence, open questions, forecasts, update freshness, relationships, and deterministic event descriptions.

## UI workflow

- Note cards and note detail pages have an **Add follow-up** action. The compact composer defaults to `updates`, provides the supported relationship types, and preserves the source note.
- The ticker workspace presents timeline, assumptions, evidence, questions, forecasts, and headline status. The Research Queue is available from desktop and mobile navigation.

## Verification

- Added `backend/tests/test_reasoning_ledger.py` for atomic follow-ups/backlinks, pending questions, ledger links, forecast resolution, conversions, challenges, histories, saved-view filtering, and review generation.
- Passed: `python -m unittest discover -s backend/tests -v` (22 tests), `node --check app-modern.js`, `node --check refresh-prices.js`, and a clean SQLite Alembic upgrade/downgrade/upgrade sequence.
