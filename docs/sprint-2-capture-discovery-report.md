# Sprint 2 capture and discovery report

## Data model and migration

`e5f6a7b8c9d0_sprint2_capture_discovery` adds metric cards, ideas and ticker links, weekly-review records, and saved-view sort/column/pinning metadata.

## Storage

Binary attachment capture is intentionally deferred until production object storage is provisioned. Source capture remains text, URL, table/CSV, and manual-metric based; the application does not persist binary blobs in the relational database.

## APIs

- `POST/GET /api/metric-cards`, `POST /api/tables/parse`, `POST /api/charts`
- `POST/GET /api/ideas`, `POST /api/ideas/{id}/promote`
- `GET /api/workspaces/daily`, `POST /api/workspaces/weekly`
- `GET /api/patterns`
- `POST/GET /api/saved-views`, `GET /api/saved-views/{id}/results`, `GET /api/saved-views/defaults`

## UI workflows

The keyboard command palette (`Ctrl/Cmd+K`) opens daily workspace, weekly review, Idea Lab, Patterns, capture, research queue, reviews, note composition, follow-up, and question capture. `N`, `Q`, and `F` are available outside text fields; `Escape` closes overlay UI.

## Deterministic rules

Patterns surface ticker research volume without a thesis, unresolved-question backlogs, forecast accuracy and signed-error bias, challenged-assumption backlogs, and terminal-call invalidation rate. Every result carries its rule, count, linked IDs when applicable, and a low-sample indicator.

## Verification

`python -m unittest discover -s backend/tests -v` passed 23 tests. `node --check app-modern.js` and `node --check refresh-prices.js` passed. A clean SQLite Alembic upgrade to `e5f6a7b8c9d0` passed.

## Deferred feature

Image, PDF, audio, clipboard image, and drag/drop attachment capture will ship with the future object-storage version.
