"""Transactional persistence and presentation helpers for the journal API."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    CallBenchmarkSnapshot,
    CallEvent,
    Note,
    NoteRevision,
    NoteSecurityMention,
    NoteTag,
    Security,
    SecurityPrice,
    Tag,
    TrackedCall,
    TrackedCallLeg,
)
from .returns import canonical_return_object


def _security(session: Session, symbol: str) -> Security:
    security = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not security:
        security = Security(symbol=symbol.upper())
        session.add(security)
        session.flush()
    return security


def _record_quote(session: Session, security: Security, quote) -> None:
    session.add(SecurityPrice(
        security_id=security.id,
        timestamp=quote.timestamp,
        raw_price=quote.price,
        adjusted_price=quote.price,
        price_type=quote.price_type,
        provider=quote.provider,
    ))


def _latest_price(session: Session, security_id: str, fallback: float) -> float:
    value = session.scalar(
        select(SecurityPrice.raw_price)
        .where(SecurityPrice.security_id == security_id)
        .order_by(SecurityPrice.timestamp.desc(), SecurityPrice.retrieved_at.desc())
        .limit(1)
    )
    return float(value) if value is not None else float(fallback)


def _latest_quote_metadata(session: Session, security_id: str, fallback: float) -> tuple[float, dict]:
    price = session.scalar(
        select(SecurityPrice).where(SecurityPrice.security_id == security_id)
        .order_by(SecurityPrice.timestamp.desc(), SecurityPrice.retrieved_at.desc()).limit(1)
    )
    if not price:
        return float(fallback), {"provider": "entry_record", "price_type": "entry", "timestamp": None}
    return float(price.raw_price), {"provider": price.provider, "price_type": price.price_type, "timestamp": price.timestamp}


def call_return_object(session: Session, call: TrackedCall) -> dict:
    legs = session.scalars(select(TrackedCallLeg).where(TrackedCallLeg.tracked_call_id == call.id).order_by(TrackedCallLeg.leg_order)).all()
    benchmark = session.scalar(select(CallBenchmarkSnapshot).where(CallBenchmarkSnapshot.tracked_call_id == call.id))
    terminal = call.status in {"closed", "invalidated"}
    leg_data = []
    for leg in legs:
        current, quote = _latest_quote_metadata(session, leg.security_id, leg.entry_price_raw)
        leg_data.append({"entry": leg.entry_price_adjusted or leg.entry_price_raw, "current": current, "exit": leg.exit_price_adjusted or leg.exit_price_raw, "direction": leg.direction})
    benchmark_current, benchmark_quote = _latest_quote_metadata(session, benchmark.benchmark_security_id, benchmark.entry_price_raw)
    return canonical_return_object(
        call_id=call.id, status=call.status, call_type=call.call_type, legs=leg_data,
        benchmark={"entry": benchmark.entry_price_adjusted or benchmark.entry_price_raw, "current": benchmark_current, "exit": benchmark.exit_price_adjusted or benchmark.exit_price_raw, "current_quote": benchmark_quote, "exit_quote": {"provider": benchmark.exit_provider, "price_type": benchmark.exit_price_type, "timestamp": benchmark.exit_quote_at}},
        opened_at=call.opened_at, as_of=call.closed_at if terminal and call.closed_at else datetime.now(timezone.utc),
    )


def _call_payload(session: Session, call: TrackedCall) -> dict:
    legs = session.scalars(
        select(TrackedCallLeg).where(TrackedCallLeg.tracked_call_id == call.id).order_by(TrackedCallLeg.leg_order)
    ).all()
    benchmark = session.scalar(select(CallBenchmarkSnapshot).where(CallBenchmarkSnapshot.tracked_call_id == call.id))
    security_by_id = {security.id: security for security in session.scalars(select(Security).where(Security.id.in_([leg.security_id for leg in legs]))).all()}
    opened = call.opened_at.astimezone().strftime("%b %d, %Y") if call.opened_at else ""
    quote_at = legs[0].entry_quote_at.isoformat() if legs else call.opened_at.isoformat()
    if call.call_type == "long_short":
        long_leg, short_leg = legs
        return {
            "id": call.id, "type": "long_short", "status": call.status, "opened": opened,
            "long": {"symbol": security_by_id[long_leg.security_id].symbol, "entry": float(long_leg.entry_price_raw), "current": _latest_price(session, long_leg.security_id, long_leg.entry_price_raw)},
            "short": {"symbol": security_by_id[short_leg.security_id].symbol, "entry": float(short_leg.entry_price_raw), "current": _latest_price(session, short_leg.security_id, short_leg.entry_price_raw)},
            "entryQuoteAt": quote_at, "priceBasis": long_leg.entry_price_type,
        }
    leg = legs[0]
    return {
        "id": call.id, "type": call.call_type, "status": call.status, "opened": opened,
        "symbol": security_by_id[leg.security_id].symbol, "entry": float(leg.entry_price_raw),
        "current": _latest_price(session, leg.security_id, leg.entry_price_raw),
        "spyEntry": float(benchmark.entry_price_raw),
        "spyCurrent": _latest_price(session, benchmark.benchmark_security_id, benchmark.entry_price_raw),
        "entryQuoteAt": quote_at, "priceBasis": leg.entry_price_type,
    }


def serialize_call(session: Session, call: TrackedCall) -> dict:
    return _call_payload(session, call)


def serialize_note(session: Session, note: Note) -> dict:
    """Produce the existing browser shape from normalized records.

    Legacy notes retain their read-only ``metadata_json.frontend`` payload;
    all newly created call data is built from relational rows.
    """
    tags = session.scalars(select(Tag.display_name).join(NoteTag, NoteTag.tag_id == Tag.id).where(NoteTag.note_id == note.id)).all()
    tickers = session.scalars(select(Security.symbol).join(NoteSecurityMention, NoteSecurityMention.security_id == Security.id).where(NoteSecurityMention.note_id == note.id)).all()
    calls = session.scalars(select(TrackedCall).where(TrackedCall.originating_note_id == note.id).order_by(TrackedCall.created_at)).all()
    legacy = (note.metadata_json or {}).get("frontend", {})
    result = {
        "id": note.id, "type": note.type, "title": note.title or "", "body": note.body,
        "status": note.status, "tags": list(tags) or legacy.get("tags", []),
        "tickers": list(tickers) or legacy.get("tickers", []),
        "date": (note.published_at or note.created_at).astimezone().strftime("%b %d, %Y"),
        "time": (note.published_at or note.created_at).astimezone().strftime("%I:%M %p").lstrip("0"),
    }
    normalized_calls = [_call_payload(session, call) for call in calls]
    result["calls"] = normalized_calls or legacy.get("calls") or ([legacy["call"]] if legacy.get("call") else [])
    if len(result["calls"]) == 1:
        result["call"] = result["calls"][0]
    return result


def create_note(
    session: Session, *, user_id: str, parsed: dict, title: str, status: str,
    quotes: dict[str, object] | None = None,
) -> Note:
    """Persist a note and all normalized journal records atomically."""
    now = datetime.now(timezone.utc)
    note = Note(
        user_id=user_id, type=parsed["note_type"], title=title or None,
        body=parsed["clean_body"], status=status,
        published_at=now if status == "published" else None,
        metadata_json={"frontend": {"source": "api", "schema": 2}},
    )
    session.add(note)
    session.flush()
    session.add(NoteRevision(note_id=note.id, user_id=user_id, revision_number=1, title=note.title, body=note.body, type=note.type))

    for tag_name in parsed["tags"]:
        tag = session.scalar(select(Tag).where(Tag.normalized_name == tag_name.lower()))
        if not tag:
            tag = Tag(normalized_name=tag_name.lower(), display_name=tag_name)
            session.add(tag)
            session.flush()
        session.add(NoteTag(note_id=note.id, tag_id=tag.id))
    for symbol in parsed["ticker_mentions"]:
        security = _security(session, symbol)
        session.add(NoteSecurityMention(note_id=note.id, security_id=security.id, raw_token=f"${symbol}"))

    if status != "published" or not parsed["tracked_calls"]:
        return note
    if not quotes or "SPY" not in quotes:
        raise ValueError("Reference quotes are required for tracked calls")
    spy = _security(session, "SPY")
    _record_quote(session, spy, quotes["SPY"])
    for request in parsed["tracked_calls"]:
        call = TrackedCall(
            user_id=user_id, originating_note_id=note.id, call_type=request["type"],
            status="open", benchmark_security_id=spy.id, opened_at=now,
            legacy_metadata_json={"source": "api", "schema": 2},
        )
        session.add(call)
        session.flush()
        symbols = [(request["long"], "long", 1), (request["short"], "short", 2)] if request["type"] == "long_short" else [(request["symbol"], "long" if request["type"] == "bull" else "short", 1)]
        for symbol, direction, order in symbols:
            security = _security(session, symbol)
            quote = quotes[symbol]
            _record_quote(session, security, quote)
            session.add(TrackedCallLeg(
                tracked_call_id=call.id, security_id=security.id, direction=direction, leg_order=order,
                entry_price_raw=quote.price, entry_price_adjusted=quote.price,
                entry_quote_at=quote.timestamp, entry_price_type=quote.price_type,
                entry_provider=quote.provider,
            ))
        benchmark_quote = quotes["SPY"]
        session.add(CallBenchmarkSnapshot(
            tracked_call_id=call.id, benchmark_security_id=spy.id,
            entry_price_raw=benchmark_quote.price, entry_price_adjusted=benchmark_quote.price,
            entry_quote_at=benchmark_quote.timestamp, entry_price_type=benchmark_quote.price_type,
            entry_provider=benchmark_quote.provider,
        ))
        session.add(CallEvent(note_id=note.id, event_type="opened", occurred_at=now, snapshot_json={"tracked_call_id": call.id, "source": "api"}))
    return note
