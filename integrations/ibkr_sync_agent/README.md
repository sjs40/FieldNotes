# FieldNotes IBKR Sync Agent

This local, read-only agent connects to TWS or IB Gateway and pushes snapshots
to FieldNotes. It never receives or sends orders, and TWS must never be exposed
to the public internet. Configure `FIELDNOTES_API_URL`, `FIELDNOTES_SYNC_TOKEN`,
`IBKR_HOST`, `IBKR_PORT`, and `IBKR_CLIENT_ID` locally (do not commit them).

Implement the provider with `ib_insync` or the IB API, then call the API client
in `agent.py` for a manual sync. Web API support can implement the same provider
interface later.
