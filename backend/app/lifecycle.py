"""Atomic lifecycle operations for normalized tracked calls."""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .journal import create_note, serialize_call
from .models import CallBenchmarkSnapshot, CallEvent, NoteRelationship, Security, TrackedCall, TrackedCallLeg
from .parser import parse_note

INVALIDATION_CATEGORIES = {"core_assumption_disproven", "catalyst_failed", "new_information", "reasoning_flawed", "other"}


def _quotes(session: Session, call: TrackedCall, provider):
    legs = session.scalars(select(TrackedCallLeg).where(TrackedCallLeg.tracked_call_id == call.id).order_by(TrackedCallLeg.leg_order)).all()
    benchmark = session.scalar(select(CallBenchmarkSnapshot).where(CallBenchmarkSnapshot.tracked_call_id == call.id))
    securities = session.scalars(select(Security).where(Security.id.in_([x.security_id for x in legs] + [benchmark.benchmark_security_id]))).all()
    quotes, failures = {}, {}
    for security in securities:
        try:
            quotes[security.id] = provider.get_latest_quote(security.symbol)
        except Exception as exc:
            failures[security.symbol] = str(exc)
    if failures:
        raise HTTPException(503, detail={"message": "No lifecycle change was made because every required quote must be captured first.", "failures": failures})
    return legs, benchmark, {x.id: x for x in securities}, quotes


def execute(session: Session, *, call_id: str, user_id: str, event_type: str, explanation: str, idempotency_key: str, provider, body: str | None = None, title: str = "", invalidation_category: str | None = None) -> dict:
    if event_type not in {"updated", "closed", "reversed", "invalidated"}:
        raise HTTPException(422, detail="Unsupported lifecycle event")
    call = session.scalar(select(TrackedCall).where(TrackedCall.id == call_id, TrackedCall.user_id == user_id))
    if not call:
        raise HTTPException(404, detail="Tracked call not found")
    existing = session.scalar(select(CallEvent).where(CallEvent.tracked_call_id == call.id, CallEvent.idempotency_key == idempotency_key))
    if existing:
        return {"call": serialize_call(session, call), "idempotent_replay": True}
    if call.status != "open":
        raise HTTPException(409, detail="Lifecycle actions are allowed only on open calls")
    if event_type == "invalidated" and invalidation_category not in INVALIDATION_CATEGORIES:
        raise HTTPException(422, detail="A valid invalidation category is required")

    # Validate before any writes. Updates deliberately do not need market quotes.
    if event_type == "updated":
        if not body:
            raise HTTPException(422, detail="Update text is required")
        parsed = parse_note(body, "note")
        if parsed["errors"] or parsed["tracked_calls"]:
            raise HTTPException(422, detail={"errors": parsed["errors"], "message": "Updates cannot open a new tracked call. Publish a separate note to create one."})
        update = create_note(session, user_id=user_id, parsed=parsed, title=title, status="published")
        session.add(NoteRelationship(from_note_id=update.id, to_note_id=call.originating_note_id, relationship_type="update_of"))
        session.add(CallEvent(note_id=update.id, tracked_call_id=call.id, event_type="updated", explanation=explanation, idempotency_key=idempotency_key, snapshot_json={"tracked_call_id": call.id, "update_note_id": update.id}))
        session.commit()
        return {"call": serialize_call(session, call), "update_note_id": update.id}

    legs, benchmark, securities, quotes = _quotes(session, call, provider)
    quote_snapshot = {securities[key].symbol: {"price": str(q.price), "timestamp": q.timestamp.isoformat(), "price_type": q.price_type, "provider": q.provider} for key, q in quotes.items()}
    closed_at = datetime.now(timezone.utc)
    for leg in legs:
        quote = quotes[leg.security_id]
        leg.exit_price_raw = leg.exit_price_adjusted = quote.price
        leg.exit_quote_at, leg.exit_price_type, leg.exit_provider = quote.timestamp, quote.price_type, quote.provider
    quote = quotes[benchmark.benchmark_security_id]
    benchmark.exit_price_raw = benchmark.exit_price_adjusted = quote.price
    benchmark.exit_quote_at, benchmark.exit_price_type, benchmark.exit_provider = quote.timestamp, quote.price_type, quote.provider
    call.status = "invalidated" if event_type == "invalidated" else "closed"
    call.closed_at, call.closing_reason = closed_at, explanation
    call.invalidation_category = invalidation_category if event_type == "invalidated" else None
    reversed_call = None
    if event_type == "reversed":
        reversed_call = TrackedCall(user_id=user_id, originating_note_id=call.originating_note_id, call_type={"bull": "bear", "bear": "bull"}.get(call.call_type, "long_short"), status="open", benchmark_security_id=benchmark.benchmark_security_id, opened_at=closed_at, reversed_from_call_id=call.id, legacy_metadata_json={"source": "lifecycle_reverse"})
        session.add(reversed_call); session.flush()
        # Pairs reverse by swapping both the order and direction.
        source_legs = list(reversed(legs)) if call.call_type == "long_short" else legs
        for order, old in enumerate(source_legs, 1):
            q = quotes[old.security_id]
            direction = "short" if old.direction == "long" else "long"
            session.add(TrackedCallLeg(tracked_call_id=reversed_call.id, security_id=old.security_id, direction=direction, leg_order=order, entry_price_raw=q.price, entry_price_adjusted=q.price, entry_quote_at=q.timestamp, entry_price_type=q.price_type, entry_provider=q.provider))
        q = quotes[benchmark.benchmark_security_id]
        session.add(CallBenchmarkSnapshot(tracked_call_id=reversed_call.id, benchmark_security_id=benchmark.benchmark_security_id, entry_price_raw=q.price, entry_price_adjusted=q.price, entry_quote_at=q.timestamp, entry_price_type=q.price_type, entry_provider=q.provider))
        session.add(CallEvent(note_id=call.originating_note_id, tracked_call_id=reversed_call.id, event_type="opened", explanation="Opened by reversal", snapshot_json={"reversed_from_call_id": call.id, "quotes": quote_snapshot}))
    session.add(CallEvent(note_id=call.originating_note_id, tracked_call_id=call.id, event_type=event_type, explanation=explanation, idempotency_key=idempotency_key, snapshot_json={"tracked_call_id": call.id, "status": call.status, "quotes": quote_snapshot}))
    session.commit()
    result = {"call": serialize_call(session, call)}
    if reversed_call:
        result["reversed_call"] = serialize_call(session, reversed_call)
    return result
