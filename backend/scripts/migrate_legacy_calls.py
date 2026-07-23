"""Idempotently import prototype JSON calls into the normalized journal tables.

Usage:
  python -m backend.scripts.migrate_legacy_calls --dry-run --report migration.json
  python -m backend.scripts.migrate_legacy_calls --apply --report migration.json
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import (CallBenchmarkSnapshot, CallEvent, Note,
    NoteSecurityMention, NoteTag, Security, Tag, TrackedCall, TrackedCallLeg,
    User)
from backend.app.parser import parse_note


def parse_legacy_date(value, fallback):
    if isinstance(value, str):
        for fmt in ("%b %d, %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    return fallback or datetime.now(timezone.utc)


def security(session, symbol):
    item = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not item:
        item = Security(symbol=symbol.upper())
        session.add(item); session.flush()
    return item


def legacy_calls(frontend):
    calls = list(frontend.get("calls") or [])
    single = frontend.get("call")
    if single and not any((c.get("id") and c.get("id") == single.get("id")) or c == single for c in calls):
        calls.append(single)
    return calls


def run(apply=False):
    if apply:
        # Schema creation is deliberately excluded from dry runs. Production
        # uses Alembic before this administrative data migration.
        Base.metadata.create_all(engine)
    report = {"notes_seen": 0, "calls_created": 0, "calls_skipped": 0, "mentions_created": 0, "failures": []}
    session = SessionLocal()
    try:
        user = session.get(User, "local-user")
        if not user:
            user = User(id="local-user", email="local@fieldnotes.invalid", display_name="Local user")
            session.add(user)
        for note in session.scalars(select(Note)).all():
            report["notes_seen"] += 1
            frontend = (note.metadata_json or {}).get("frontend", {})
            parsed = parse_note(note.body, note.type)
            # Tags and every ticker mention are normalized independently of calls.
            for tag_name in parsed["tags"]:
                tag = session.scalar(select(Tag).where(Tag.normalized_name == tag_name.lower()))
                if not tag:
                    tag = Tag(normalized_name=tag_name.lower(), display_name=tag_name); session.add(tag); session.flush()
                if not session.get(NoteTag, {"note_id": note.id, "tag_id": tag.id}):
                    session.add(NoteTag(note_id=note.id, tag_id=tag.id))
            for symbol in parsed["ticker_mentions"]:
                sec = security(session, symbol)
                exists = session.scalar(select(NoteSecurityMention).where(NoteSecurityMention.note_id == note.id, NoteSecurityMention.security_id == sec.id))
                if not exists:
                    session.add(NoteSecurityMention(note_id=note.id, security_id=sec.id, raw_token=f"${symbol}")); report["mentions_created"] += 1
            for legacy in legacy_calls(frontend):
                legacy_id = legacy.get("id")
                existing = session.scalar(select(TrackedCall).where(TrackedCall.originating_note_id == note.id, TrackedCall.legacy_metadata_json["legacy_id"].as_string() == str(legacy_id))) if legacy_id else None
                if existing:
                    report["calls_skipped"] += 1; continue
                try:
                    opened = parse_legacy_date(legacy.get("opened") or frontend.get("date"), note.published_at)
                    spy = security(session, "SPY")
                    call = TrackedCall(user_id=note.user_id or "local-user", originating_note_id=note.id, call_type=legacy.get("type", "bull"), status=legacy.get("status", "open"), benchmark_security_id=spy.id, opened_at=opened, legacy_metadata_json={"legacy_id": legacy_id, "source": "metadata_json.frontend", "unverified": not bool(legacy.get("entryQuoteAt")), "original": legacy})
                    session.add(call); session.flush()
                    legs = []
                    if call.call_type == "long_short":
                        legs = [(legacy["long"], "long", 1), (legacy["short"], "short", 2)]
                    else:
                        legs = [({"symbol": legacy["symbol"], "entry": legacy.get("entry"), "current": legacy.get("current")}, "long" if call.call_type == "bull" else "short", 1)]
                    for leg, direction, order in legs:
                        sec = security(session, leg["symbol"])
                        entry = leg.get("entry")
                        if not entry or float(entry) <= 0:
                            raise ValueError("legacy call has no valid entry price")
                        session.add(TrackedCallLeg(tracked_call_id=call.id, security_id=sec.id, direction=direction, leg_order=order, entry_price_raw=entry, entry_price_adjusted=entry, entry_quote_at=opened, entry_price_type=legacy.get("priceBasis", "legacy_unverified"), entry_provider="legacy", exit_price_raw=leg.get("exit")))
                    benchmark_entry = legacy.get("spyEntry") or 1
                    session.add(CallBenchmarkSnapshot(tracked_call_id=call.id, benchmark_security_id=spy.id, entry_price_raw=benchmark_entry, entry_price_adjusted=benchmark_entry, entry_quote_at=opened, entry_price_type=legacy.get("priceBasis", "legacy_unverified"), entry_provider="legacy", exit_price_raw=legacy.get("spyExit")))
                    session.add(CallEvent(note_id=note.id, event_type="opened", occurred_at=opened, snapshot_json={"tracked_call_id": call.id, "legacy": True, "call": legacy}))
                    report["calls_created"] += 1
                except Exception as exc:
                    report["failures"].append({"note_id": note.id, "call_id": legacy_id, "error": str(exc)})
                    session.rollback()
        if apply:
            session.commit()
        else:
            session.rollback()
        return report
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run(apply=args.apply)
    text = json.dumps(report, indent=2, default=str)
    if args.report: args.report.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
