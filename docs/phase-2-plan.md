# Phase 2 implementation plan

## Current compatibility shape

The static UI currently treats a note as a JSON object with `id`, `type`,
`title`, `body`, `tags`, `tickers`, `date`, `time`, and either a compatibility
`call` or a `calls` array. A call is embedded in that note and contains a
`type`, `status`, entry/current prices, optional SPY prices, or `long`/`short`
objects for a pair. The backend persists this object in
`notes.metadata_json.frontend`; `api-bridge.js` mirrors the entire browser
localStorage array to `/api/notes/sync`.

## Safe migration plan

1. Add users, normalized note relations, calls, legs, benchmarks, events, and
   revisions without dropping the existing compatibility fields.
2. Add Alembic and an idempotent legacy importer. It will read both `call` and
   `calls`, preserve original values, and mark unsupported legacy quotes rather
   than inventing them.
3. Move publication and lifecycle actions to transactional API services and a
   server-side return engine.
4. Replace whole-array localStorage sync with API reads/writes. Keep only a
   one-time explicit legacy import endpoint.
5. Build ticker, call, search, and revision endpoints from normalized tables.
6. Add local single-user session authentication, production PostgreSQL/Vercel
   configuration, and tests before removing compatibility data.

## Compatibility rule

`metadata_json.frontend`, `call`, and `calls` remain read-only import sources
until the migration report is reviewed. New call data must be written only to
normalized relational tables.
