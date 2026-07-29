# Analyst workspace roadmap

## Guiding principles

Fieldnotes will remain an evidence and decision journal, not an AI-chat layer.
New workflows must preserve source links, make expectations explicit before an
outcome is known, allow partial completion, and retain dated history instead of
overwriting prior judgment.

## Phase 1 — Company workspace foundation

Build an analyst-owned workspace for each company, backed by the existing
security master and normalized note/ticker links.

- Companies tab with followed/recent workspaces and one active company.
- Optional company description and business-model fields describing what the
  company does and how it makes money.
- Persistent active-company choice; a capture with no explicit ticker inherits
  that company, while an explicit `$TICKER` remains authoritative.
- Company overview links existing notes, calls, questions, forecasts and
  research timelines without duplicating their data.

**Acceptance criteria:** selecting a company takes one action, company context
is visible across capture surfaces, no cross-company capture is silently
misclassified, and descriptions are private to the signed-in analyst.

## Phase 2 — Markdown research capture

Keep raw Markdown as the canonical note body and add sanitized rendering.

- Keyboard-first write/preview capture with headings, lists, tables, links,
  blockquotes and task lists.
- Preserve existing `/type`, `$ticker`, `#tag`, tracker and URL parsing.
- Render only a safe Markdown subset; never execute HTML from a note.
- Continue deriving titles from the first eligible plain-text line. A first line
  containing `/`, `#`, or `$` is metadata, never a title candidate.

**Acceptance criteria:** formatting is optional, raw content remains portable,
and existing plain-text captures render unchanged.

## Phase 3 — Earnings workflow and archive

Introduce optional, linked records for each reporting period.

- Pre-earnings checklist: expectations, KPI watch list, debate questions,
  catalysts, risks and free-form notes.
- Earnings-day capture: results, guidance, KPI observations, management quotes,
  market reaction and free-form notes.
- Post-earnings review: expected-versus-actual outcomes, thesis impact,
  resolution of questions and optional decision/action.
- Historical archive by company and fiscal period, with links to normal notes
  and sources.

Every field is optional; an analyst can save an event shell, only notes, or a
single KPI without completing a template.

**Acceptance criteria:** no template blocks rapid capture, every expectation is
timestamped before its resolution, and archive rows are navigable by company.

## Phase 4 — Forecasts and KPI tracking

Extend the existing forecast ledger rather than creating a competing system.

- Quantitative point/range forecasts with unit, period, confidence, rationale
  and actual value.
- Qualitative forecasts with expected outcome, confidence, resolution event and
  correct/partly-correct/incorrect status.
- Reusable KPI definitions per company and KPI observations per reporting
  period.
- Scorecards compare analyst expectations with reported actuals and retain each
  revised forecast as a dated record.

**Acceptance criteria:** forecasts can exist outside earnings, resolution never
rewrites an original expectation, and score calculations are deterministic.

## Phase 5 — Reviews, scorecards and hardening

Turn the recorded history into a consistent analyst review process.

- Company review queue for stale descriptions, unresolved questions, upcoming
  earnings, unresolved forecasts and missing post-earnings reviews.
- Forecast-accuracy and qualitative-calibration scorecards.
- Cross-company KPI and earnings comparison views.
- Exportable investment memo, earnings preview/review and company timeline.
- Permission, migration, performance, mobile and audit-log hardening.

**Acceptance criteria:** review prompts are derived from durable data, exports
cite their underlying notes/sources, and all historical decisions remain
auditable.

## Delivery order

Complete and verify Phase 1 before enabling Markdown. Then deliver the earnings
event model and pre-earnings workflow before adding forecast/KPI resolution and
scorecards. This sequence creates a usable daily workflow at each release rather
than waiting for a large all-at-once launch.
