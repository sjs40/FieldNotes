from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, get_session
from .config import settings
from .models import CallBenchmarkSnapshot, CallEvent, Note, Security, SecurityPrice, Tag, TrackedCall, TrackedCallLeg
from .parser import parse_note
from .market_data import YFinanceMarketDataProvider
from .auth import CurrentUser, get_current_user
from .journal import create_note, serialize_note as serialize_journal_note

app = FastAPI(title="Fieldnotes API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"], allow_methods=["*"], allow_headers=["*"])


def run_production_migrations() -> None:
    """Apply committed Alembic revisions before a production instance serves."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    command.upgrade(config, "head")


class ParseRequest(BaseModel):
    body: str
    note_type: str = "note"


class SyncRequest(BaseModel):
    notes: list[dict]


class PublishRequest(BaseModel):
    body: str
    note_type: str = "note"
    title: str = ""


class LifecycleRequest(BaseModel):
    explanation: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    symbols: list[str] = []


class BackfillRequest(BaseModel):
    notes: list[dict]


def serialized_note(session: Session, note: Note) -> dict:
    return serialize_journal_note(session, note)


def record_frontend_note(session: Session, incoming: dict) -> Note:
    note = session.get(Note, str(incoming.get("id"))) if incoming.get("id") else None
    parsed = parse_note(incoming.get("body", ""), incoming.get("type", "note"))
    if note is None:
        note = Note()
        if incoming.get("id"):
            note.id = str(incoming["id"])
        session.add(note)
    note.type = parsed["note_type"]
    note.title = incoming.get("title") or None
    note.body = parsed["clean_body"]
    note.status = incoming.get("status", "published")
    note.published_at = note.published_at or datetime.now(timezone.utc)
    note.metadata_json = {"frontend": {**incoming, "type": note.type, "body": note.body, "tags": parsed["tags"], "tickers": parsed["ticker_mentions"]}}
    for tag_name in parsed["tags"]:
        existing = session.scalar(select(Tag).where(Tag.normalized_name == tag_name.lower()))
        if not existing:
            session.add(Tag(normalized_name=tag_name.lower(), display_name=tag_name))
    for symbol in parsed["ticker_mentions"] + ["SPY"]:
        existing = session.scalar(select(Security).where(Security.symbol == symbol))
        if not existing:
            session.add(Security(symbol=symbol))
    return note


@app.on_event("startup")
def bootstrap() -> None:
    # Local convenience only. In production migrations run through Alembic,
    # never through SQLAlchemy metadata creation.
    if not settings.is_production:
        Base.metadata.create_all(engine)
        return
    if not settings.authentication_enabled:
        raise RuntimeError("Supabase authentication must be configured in production")
    run_production_migrations()


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": "yfinance"}


@app.get("/api/auth/me")
async def current_user(user: CurrentUser = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.get("/api/auth/config")
def auth_config():
    """Publish only the Supabase URL and publishable key; never expose secrets."""
    return {"enabled": settings.authentication_enabled, "url": settings.supabase_url, "publishable_key": settings.supabase_publishable_key}


@app.post("/api/notes/parse")
def parse(payload: ParseRequest):
    return parse_note(payload.body, payload.note_type)


@app.get("/api/notes")
async def list_notes(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    return [serialized_note(session, note) for note in session.scalars(select(Note).where(Note.user_id == user.id).order_by(Note.created_at.desc())).all()]


@app.post("/api/notes")
async def create_draft(payload: PublishRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"]})
    note = create_note(session, user_id=user.id, parsed=parsed, title=payload.title, status="draft")
    session.commit()
    return serialized_note(session, note)


@app.post("/api/notes/sync")
def sync_notes(payload: SyncRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """Legacy-only import bridge; new browser writes use individual note APIs."""
    for incoming in payload.notes:
        note = record_frontend_note(session, incoming)
        note.user_id = user.id
    session.commit()
    return {"notes": [serialized_note(session, note) for note in session.scalars(select(Note).where(Note.user_id == user.id).order_by(Note.created_at.desc())).all()]}


@app.post("/api/notes/publish")
async def publish_note(payload: PublishRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """Create every explicitly requested tracker with a backend-captured quote.

    Calls are never created without a reference quote; ordinary notes remain
    publishable even if the market-data provider is unavailable.
    """
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"] or parsed["warnings"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"], "warnings": parsed["warnings"]})
    provider = YFinanceMarketDataProvider()
    quote_failures = {}
    symbols = {"SPY"}
    for call in parsed["tracked_calls"]:
        symbols.update([call.get("symbol"), call.get("long"), call.get("short")])
    symbols.discard(None)
    quotes = {}
    for symbol in symbols:
        try:
            quote = provider.get_latest_quote(symbol)
            quotes[symbol] = quote
        except Exception as exc:
            quote_failures[symbol] = str(exc)
    if parsed["tracked_calls"] and quote_failures:
        raise HTTPException(status_code=503, detail={"message": "Tracked calls were not published because a reference quote could not be captured.", "failures": quote_failures})
    note = create_note(session, user_id=user.id, parsed=parsed, title=payload.title, status="published", quotes=quotes)
    session.commit()
    return serialized_note(session, note)


@app.post("/api/capture")
def capture(payload: ParseRequest, session: Session = Depends(get_session)):
    parsed = parse_note(payload.body, payload.note_type)
    note = record_frontend_note(session, {"type": parsed["note_type"], "body": parsed["clean_body"], "status": "draft", "tags": parsed["tags"], "tickers": parsed["ticker_mentions"]})
    session.commit()
    return {"note": serialized_note(session, note), "parse": parsed}


@app.post("/api/market-data/refresh")
def refresh(payload: RefreshRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    symbols = {symbol.upper() for symbol in payload.symbols}
    if not symbols:
        symbols = set(session.scalars(
            select(Security.symbol)
            .join(TrackedCallLeg, TrackedCallLeg.security_id == Security.id)
            .join(TrackedCall, TrackedCall.id == TrackedCallLeg.tracked_call_id)
            .where(TrackedCall.user_id == user.id, TrackedCall.status == "open")
        ).all())
        symbols.update(session.scalars(
            select(Security.symbol)
            .join(CallBenchmarkSnapshot, CallBenchmarkSnapshot.benchmark_security_id == Security.id)
            .join(TrackedCall, TrackedCall.id == CallBenchmarkSnapshot.tracked_call_id)
            .where(TrackedCall.user_id == user.id, TrackedCall.status == "open")
        ).all())
    symbols.add("SPY")
    provider = YFinanceMarketDataProvider()
    quotes = {}
    failures = {}
    for symbol in sorted(symbols):
        try:
            quote = provider.get_latest_quote(symbol)
            security = session.scalar(select(Security).where(Security.symbol == symbol))
            if not security:
                security = Security(symbol=symbol)
                session.add(security)
                session.flush()
            session.add(SecurityPrice(security_id=security.id, timestamp=quote.timestamp, raw_price=quote.price, adjusted_price=quote.price, price_type=quote.price_type, provider=quote.provider))
            quotes[symbol] = {"price": quote.price, "timestamp": quote.timestamp.isoformat(), "basis": quote.price_type, "provider": quote.provider}
        except Exception as exc:
            failures[symbol] = str(exc)
    session.commit()
    if not quotes:
        raise HTTPException(status_code=503, detail={"message": "No quotes could be retrieved.", "failures": failures})
    return {"quotes": quotes, "failures": failures}


@app.post("/api/market-data/backfill-legacy")
def backfill_legacy_entries(payload: BackfillRequest):
    """Replace pre-backend demo entries with auditable historical closes."""
    provider = YFinanceMarketDataProvider()
    failures = []
    for note in payload.notes:
        for call in note.get("calls") or ([note["call"]] if note.get("call") else []):
            if call.get("entryQuoteAt"):
                continue
            try:
                date_text = call.get("opened") or note.get("date")
                if call.get("type") == "long_short":
                    for leg_name in ("long", "short"):
                        leg = call[leg_name]
                        quote = provider.get_historical_close(leg["symbol"], date_text)
                        leg["entry"] = quote.price
                    call["priceBasis"] = "historical_close"
                else:
                    quote = provider.get_historical_close(call["symbol"], date_text)
                    spy = provider.get_historical_close("SPY", date_text)
                    call["entry"] = quote.price
                    call["spyEntry"] = spy.price
                    call["priceBasis"] = "historical_close"
                call["entryQuoteAt"] = f"{date_text} regular-session close"
                call.pop("unverified", None)
            except Exception as exc:
                failures.append({"note": note.get("id"), "call": call.get("symbol", call.get("type")), "error": str(exc)})
    return {"notes": payload.notes, "failures": failures}


@app.post("/api/calls/{note_id}/{event_type}")
def lifecycle(note_id: str, event_type: str, payload: LifecycleRequest, session: Session = Depends(get_session)):
    if event_type not in {"updated", "closed", "reversed", "invalidated"}:
        raise HTTPException(status_code=422, detail="Unsupported lifecycle event")
    note = session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    call = note.metadata_json.get("frontend", {}).get("call")
    if not call:
        raise HTTPException(status_code=422, detail="This note has no tracked call")
    if event_type in {"closed", "invalidated", "reversed"}:
        call["status"] = "invalidated" if event_type == "invalidated" else "closed"
    note.metadata_json["frontend"]["call"] = call
    session.add(CallEvent(note_id=note.id, event_type=event_type, explanation=payload.explanation, snapshot_json={"call": call}))
    session.commit()
    return serialized_note(session, note)


@app.get("/api/export/calls.csv")
def export_calls(session: Session = Depends(get_session)):
    rows = ["Call,Type,Status,Opened,Entry,Current"]
    for note in session.scalars(select(Note)).all():
        call = note.metadata_json.get("frontend", {}).get("call")
        if call:
            symbol = call.get("symbol") or f"{call['long']['symbol']}/{call['short']['symbol']}"
            rows.append(f"{symbol},{call.get('type','')},{call.get('status','')},{call.get('opened','')},{call.get('entry','')},{call.get('current','')}")
    return "\n".join(rows)


web_root = Path(__file__).parents[2]
app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
