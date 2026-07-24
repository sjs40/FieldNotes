from datetime import datetime, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from .database import Base, engine, get_session
from .config import settings
from .models import BrokerageAccount, BrokerageConnection, CallBenchmarkSnapshot, CallEvent, CallExpectation, Note, NoteRelationship, NoteRevision, NoteSecurityMention, NoteTag, PortfolioPosition, Security, SecurityPrice, Tag, ThesisDetails, ThesisReview, TrackedCall, TrackedCallLeg, UserReviewSettings
from .parser import parse_note
from .market_data import YFinanceMarketDataProvider
from .auth import CurrentUser, get_current_user
from .journal import call_return_object, create_note, replace_note_relationships, serialize_call, serialize_note as serialize_journal_note
from .lifecycle import execute as execute_lifecycle
from .observability import RequestObservabilityMiddleware, init_sentry, log_event
from hashlib import sha256
from .reviews import OUTCOMES, REVIEW_TYPES, STATUSES, generate as generate_reviews, serialize_review, settings_for
from .timeline import thinking_evolution, ticker_timeline

app = FastAPI(title="Fieldnotes API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestObservabilityMiddleware)


class ParseRequest(BaseModel):
    body: str
    note_type: str = "note"


class SyncRequest(BaseModel):
    notes: list[dict]


class PublishRequest(BaseModel):
    body: str
    note_type: str = "note"
    title: str = ""
    thesis_details: dict | None = None


class EditNoteRequest(BaseModel):
    body: str
    note_type: str = "note"
    title: str = ""


class LifecycleRequest(BaseModel):
    explanation: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=128)
    invalidation_category: str | None = None
    body: str | None = None
    title: str = ""
    confidence_before: str | None = None
    confidence_after: str | None = None
    thesis_state: str | None = None
    allow_snapshot_unavailable: bool = False


class RefreshRequest(BaseModel):
    symbols: list[str] = []


class BackfillRequest(BaseModel):
    notes: list[dict]

class ExpectationRequest(BaseModel):
    target_value: float | None = None
    target_type: str = "security_price"
    target_unit: str = "USD"
    explanation: str = Field(min_length=1)

class IBKRSyncRequest(BaseModel):
    user_id: str
    connection_name: str = "Interactive Brokers"
    account_id: str
    account_type: str | None = None
    base_currency: str = "USD"
    snapshot_at: datetime
    positions: list[dict]

class ReviewCompleteRequest(BaseModel):
    outcome: str
    explanation: str | None = None
    confidence_before: str | None = None
    confidence_after: str | None = None
    thesis_state_before: str | None = None
    thesis_state_after: str | None = None
    next_review_at: datetime | None = None

class ReviewSnoozeRequest(BaseModel):
    snooze_until: datetime
    explanation: str | None = None

class ReviewSettingsRequest(BaseModel):
    stale_warning_days: int = Field(default=45, ge=1)
    stale_critical_days: int = Field(default=90, ge=1)
    absolute_move_threshold: float = Field(default=.10, gt=0)
    relative_move_threshold: float = Field(default=.08, gt=0)
    daily_move_threshold: float = Field(default=.08, gt=0)


def serialized_note(session: Session, note: Note) -> dict:
    result = serialize_journal_note(session, note)
    details = session.scalar(select(ThesisDetails).where(ThesisDetails.note_id == note.id))
    if details:
        result["thesis_details"] = {"core_thesis": details.core_thesis, "key_evidence": details.key_evidence_json, "catalysts": details.catalysts_json, "risks": details.risks_json, "invalidation_conditions": details.invalidation_conditions_json, "valuation_notes": details.valuation_notes, "expected_time_horizon_days": details.expected_time_horizon_days, "review_at": details.review_at.isoformat() if details.review_at else None}
    return result

def save_thesis_details(session: Session, note_id: str, payload: dict | None) -> None:
    if not payload:
        return
    allowed = {"core_thesis", "valuation_notes", "expected_time_horizon_days", "review_at"}
    lists = {"key_evidence": "key_evidence_json", "catalysts": "catalysts_json", "risks": "risks_json", "invalidation_conditions": "invalidation_conditions_json"}
    values = {key: value for key, value in payload.items() if key in allowed}
    values.update({column: payload.get(key, []) for key, column in lists.items()})
    session.add(ThesisDetails(note_id=note_id, **values))


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
    init_sentry()
    if not settings.is_production:
        Base.metadata.create_all(engine)
        return
    settings.validate_production()


@app.get("/api/health")
def health():
    return {"status": "ok", "provider": "yfinance"}

@app.get("/api/health/live")
def health_live(request: Request):
    return {"status": "live", "request_id": request.state.request_id}

@app.get("/api/health/ready")
def health_ready(request: Request, session: Session = Depends(get_session)):
    try:
        session.execute(select(1))
        settings.validate_production()
        from alembic.runtime.migration import MigrationContext
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        with engine.connect() as connection: current = MigrationContext.configure(connection).get_current_revision()
        expected = ScriptDirectory.from_config(Config(str(Path(__file__).parents[2] / "alembic.ini"))).get_current_head()
        usable = current == expected or not settings.is_production
        response = {"status": "ready" if usable else "not_ready", "database": "ok", "authentication": "configured" if settings.authentication_enabled else "local_development", "migration_revision": current, "expected_revision": expected, "market_data_provider": "yfinance" if settings.allow_yfinance else "disabled", "request_id": request.state.request_id}
        if not usable: raise HTTPException(status_code=503, detail=response)
        return response
    except HTTPException: raise
    except Exception as exc:
        log_event("readiness_failure", "ERROR", error_class=type(exc).__name__)
        raise HTTPException(status_code=503, detail={"status": "not_ready", "database": "unavailable", "request_id": request.state.request_id})


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
async def list_notes(note_type: str | None = None, status: str | None = None, ticker: str | None = None, tag: str | None = None, has_call: bool | None = None, call_type: str | None = None, call_status: str | None = None, edited: bool | None = None, has_updates: bool | None = None, date_from: datetime | None = None, date_to: datetime | None = None, sort: str = "newest", limit: int = 100, offset: int = 0, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(Note).where(Note.user_id == user.id)
    if note_type: statement = statement.where(Note.type == note_type)
    if status: statement = statement.where(Note.status == status)
    if ticker: statement = statement.join(NoteSecurityMention, NoteSecurityMention.note_id == Note.id).join(Security, Security.id == NoteSecurityMention.security_id).where(Security.symbol == ticker.upper())
    if tag: statement = statement.join(NoteTag, NoteTag.note_id == Note.id).join(Tag, Tag.id == NoteTag.tag_id).where(Tag.normalized_name == tag.lower())
    if has_call is True: statement = statement.where(select(TrackedCall.id).where(TrackedCall.originating_note_id == Note.id).exists())
    if has_call is False: statement = statement.where(~select(TrackedCall.id).where(TrackedCall.originating_note_id == Note.id).exists())
    if call_type: statement = statement.where(select(TrackedCall.id).where(TrackedCall.originating_note_id == Note.id, TrackedCall.call_type == call_type).exists())
    if call_status: statement = statement.where(select(TrackedCall.id).where(TrackedCall.originating_note_id == Note.id, TrackedCall.status == call_status).exists())
    if edited is True: statement = statement.where(select(func.count(NoteRevision.id)).where(NoteRevision.note_id == Note.id).scalar_subquery() > 1)
    if has_updates is True: statement = statement.where(select(NoteRelationship.id).where(NoteRelationship.to_note_id == Note.id, NoteRelationship.relationship_type == "update_of").exists())
    if date_from: statement = statement.where(Note.created_at >= date_from)
    if date_to: statement = statement.where(Note.created_at <= date_to)
    order = Note.created_at.asc() if sort == "oldest" else Note.updated_at.desc() if sort == "recently_edited" else Note.created_at.desc()
    notes = session.scalars(statement.distinct().order_by(order).offset(max(0, offset)).limit(min(max(1, limit), 200))).all()
    return [serialized_note(session, note) for note in notes]


@app.post("/api/notes")
async def create_draft(payload: PublishRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"]})
    note = create_note(session, user_id=user.id, parsed=parsed, title=payload.title, status="draft")
    save_thesis_details(session, note.id, payload.thesis_details)
    session.commit()
    return serialized_note(session, note)


@app.get("/api/notes/search")
async def search_notes(q: str = "", limit: int = 100, offset: int = 0, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    query = q.strip()
    if not query:
        return []
    pattern = f"%{query}%"
    notes = session.scalars(
        select(Note).outerjoin(NoteTag, NoteTag.note_id == Note.id).outerjoin(Tag, Tag.id == NoteTag.tag_id).outerjoin(NoteSecurityMention, NoteSecurityMention.note_id == Note.id).outerjoin(Security, Security.id == NoteSecurityMention.security_id).outerjoin(CallEvent, CallEvent.note_id == Note.id).where(
            Note.user_id == user.id,
            or_(Note.title.ilike(pattern), Note.body.ilike(pattern), Tag.display_name.ilike(pattern), Security.symbol.ilike(pattern), Security.company_name.ilike(pattern), CallEvent.explanation.ilike(pattern)),
        ).distinct().order_by(Note.created_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 200))
    ).all()
    return [serialized_note(session, note) for note in notes]


@app.get("/api/notes/{note_id}/revisions")
async def list_revisions(note_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    note = session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    revisions = session.scalars(select(NoteRevision).where(NoteRevision.note_id == note.id).order_by(NoteRevision.revision_number.desc())).all()
    return [{"id": revision.id, "revision_number": revision.revision_number, "title": revision.title or "", "body": revision.body, "type": revision.type, "edited_at": revision.edited_at.isoformat()} for revision in revisions]


@app.put("/api/notes/{note_id}")
async def edit_note(note_id: str, payload: EditNoteRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    note = session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"]})
    if parsed["tracked_calls"]:
        raise HTTPException(status_code=422, detail="Editing a note cannot open, close, or remove historical calls. Publish a separate note for new tracking syntax.")
    revision_number = (session.scalar(select(func.max(NoteRevision.revision_number)).where(NoteRevision.note_id == note.id)) or 0) + 1
    note.title = payload.title or None; note.body = parsed["clean_body"]; note.type = parsed["note_type"]
    replace_note_relationships(session, note, parsed)
    session.add(NoteRevision(note_id=note.id, user_id=user.id, revision_number=revision_number, title=note.title, body=note.body, type=note.type))
    session.commit()
    return serialized_note(session, note)


@app.get("/api/calls")
async def list_calls(status: str | None = None, call_type: str | None = None, ticker: str | None = None, tag: str | None = None, date_from: datetime | None = None, date_to: datetime | None = None, sort: str = "newest", limit: int = 100, offset: int = 0, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    statement = select(TrackedCall).where(TrackedCall.user_id == user.id)
    if status:
        statement = statement.where(TrackedCall.status == status)
    if call_type: statement = statement.where(TrackedCall.call_type == call_type)
    if ticker: statement = statement.join(TrackedCallLeg, TrackedCallLeg.tracked_call_id == TrackedCall.id).join(Security, Security.id == TrackedCallLeg.security_id).where(Security.symbol == ticker.upper())
    if tag: statement = statement.join(Note, Note.id == TrackedCall.originating_note_id).join(NoteTag, NoteTag.note_id == Note.id).join(Tag, Tag.id == NoteTag.tag_id).where(Tag.normalized_name == tag.lower())
    if date_from: statement = statement.where(TrackedCall.opened_at >= date_from)
    if date_to: statement = statement.where(TrackedCall.opened_at <= date_to)
    order = TrackedCall.opened_at.asc() if sort == "oldest" else TrackedCall.closed_at.desc() if sort == "closed" else TrackedCall.opened_at.desc()
    calls = session.scalars(statement.distinct().order_by(order).offset(max(0, offset)).limit(min(max(1, limit), 200))).all()
    result = []
    for call in calls:
        note = session.get(Note, call.originating_note_id)
        result.append({"note_id": call.originating_note_id, "note_title": note.title if note else None, "call": serialize_call(session, call)})
    return result


@app.get("/api/calls/{call_id}/returns")
async def call_returns(call_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    call = session.scalar(select(TrackedCall).where(TrackedCall.id == call_id, TrackedCall.user_id == user.id))
    if not call:
        raise HTTPException(status_code=404, detail="Tracked call not found")
    return call_return_object(session, call)


@app.get("/api/calls/{call_id}")
async def call_detail(call_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    call = session.scalar(select(TrackedCall).where(TrackedCall.id == call_id, TrackedCall.user_id == user.id))
    if not call:
        raise HTTPException(status_code=404, detail="Tracked call not found")
    note = session.scalar(select(Note).where(Note.id == call.originating_note_id, Note.user_id == user.id))
    events = session.scalars(select(CallEvent).where(CallEvent.tracked_call_id == call.id).order_by(CallEvent.occurred_at.asc())).all()
    updates = session.scalars(
        select(Note).join(NoteRelationship, NoteRelationship.from_note_id == Note.id)
        .where(NoteRelationship.to_note_id == call.originating_note_id, NoteRelationship.relationship_type == "update_of", Note.user_id == user.id)
        .order_by(Note.created_at.asc())
    ).all()
    return {
        "call": serialize_call(session, call),
        "returns": call_return_object(session, call),
        "originating_note": serialized_note(session, note) if note else None,
        "updates": [serialized_note(session, update) for update in updates],
        "events": [{"id": event.id, "type": event.event_type, "occurred_at": event.occurred_at.isoformat(), "explanation": event.explanation, "snapshot": event.snapshot_json} for event in events],
        "reversed_from_call_id": call.reversed_from_call_id,
    }

@app.post("/api/calls/{call_id}/expectation")
def revise_expectation(call_id: str, payload: ExpectationRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    call = session.scalar(select(TrackedCall).where(TrackedCall.id == call_id, TrackedCall.user_id == user.id))
    if not call: raise HTTPException(404, "Tracked call not found")
    if payload.target_type == "security_price" and (payload.target_value is None or payload.target_value <= 0): raise HTTPException(422, "Target price must be positive")
    old = session.scalar(select(CallExpectation).where(CallExpectation.tracked_call_id == call.id).order_by(CallExpectation.created_at.desc()))
    session.add(CallExpectation(tracked_call_id=call.id, target_type=payload.target_type, target_value=payload.target_value, target_unit=payload.target_unit))
    session.add(CallEvent(note_id=call.originating_note_id, tracked_call_id=call.id, event_type="expectation_updated", explanation=payload.explanation, snapshot_json={"old_target": float(old.target_value) if old and old.target_value is not None else None, "new_target": payload.target_value}))
    session.commit()
    return {"call": serialize_call(session, call)}

def _sync_authorized(request: Request) -> None:
    token = request.headers.get("X-FieldNotes-Sync-Token", "")
    if not settings.ibkr_sync_token or not token or token != settings.ibkr_sync_token:
        raise HTTPException(status_code=401, detail="Invalid sync credential")

@app.post("/api/integrations/ibkr/sync")
def ibkr_sync(payload: IBKRSyncRequest, request: Request, session: Session = Depends(get_session)):
    _sync_authorized(request)
    account_hash = sha256(payload.account_id.encode()).hexdigest()
    connection = session.scalar(select(BrokerageConnection).where(BrokerageConnection.user_id == payload.user_id, BrokerageConnection.provider == "ibkr"))
    if not connection:
        connection = BrokerageConnection(user_id=payload.user_id, provider="ibkr", display_name=payload.connection_name); session.add(connection); session.flush()
    account = session.scalar(select(BrokerageAccount).where(BrokerageAccount.connection_id == connection.id, BrokerageAccount.external_account_id_hash == account_hash))
    if not account:
        account = BrokerageAccount(connection_id=connection.id, external_account_id_hash=account_hash, display_name="IBKR account •" + payload.account_id[-4:], account_type=payload.account_type, base_currency=payload.base_currency); session.add(account); session.flush()
    existing = session.scalar(select(PortfolioPosition).where(PortfolioPosition.brokerage_account_id == account.id, PortfolioPosition.snapshot_at == payload.snapshot_at))
    if existing: return {"status": "ok", "idempotent_replay": True}
    for row in payload.positions:
        symbol = str(row["symbol"]).upper(); security = session.scalar(select(Security).where(Security.symbol == symbol)) or Security(symbol=symbol, currency=row.get("currency", payload.base_currency)); session.add(security); session.flush()
        session.add(PortfolioPosition(brokerage_account_id=account.id, security_id=security.id, external_contract_id=row.get("contract_id"), quantity=row["quantity"], average_cost=row.get("average_cost"), market_price=row.get("market_price"), market_value=row.get("market_value"), unrealized_pnl=row.get("unrealized_pnl"), realized_pnl=row.get("realized_pnl"), currency=row.get("currency", payload.base_currency), snapshot_at=payload.snapshot_at, metadata_json={"source": "ibkr_sync_agent"}))
    connection.last_synced_at = account.last_synced_at = payload.snapshot_at; session.commit(); log_event("ibkr_sync", user_id=payload.user_id, position_count=len(payload.positions))
    return {"status": "ok", "idempotent_replay": False}

@app.get("/api/portfolio/accounts")
def portfolio_accounts(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    return [{"id": a.id, "display_name": a.display_name, "base_currency": a.base_currency, "last_synced_at": a.last_synced_at} for a in session.scalars(select(BrokerageAccount).join(BrokerageConnection).where(BrokerageConnection.user_id == user.id)).all()]

@app.get("/api/portfolio/positions")
@app.get("/api/portfolio")
def portfolio(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.execute(select(PortfolioPosition, Security).join(Security).join(BrokerageAccount).join(BrokerageConnection).where(BrokerageConnection.user_id == user.id).order_by(PortfolioPosition.snapshot_at.desc())).all()
    latest = {}
    for position, security in rows: latest.setdefault((position.brokerage_account_id, security.id), {"security_id": security.id, "symbol": security.symbol, "quantity": float(position.quantity), "average_cost": float(position.average_cost) if position.average_cost is not None else None, "market_price": float(position.market_price) if position.market_price is not None else None, "market_value": float(position.market_value) if position.market_value is not None else None, "unrealized_pnl": float(position.unrealized_pnl) if position.unrealized_pnl is not None else None, "snapshot_at": position.snapshot_at})
    return list(latest.values())

@app.get("/api/portfolio/positions/{security_id}")
def portfolio_security(security_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    positions = portfolio(user, session)
    return [row for row in positions if row["security_id"] == security_id]

@app.get("/api/portfolio/coverage")
def portfolio_coverage(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """Research coverage is descriptive only; holdings never imply a call stance."""
    rows=portfolio(user,session); now=datetime.now(timezone.utc); result=[]
    for row in rows:
        notes=session.scalars(select(Note).join(NoteSecurityMention).where(Note.user_id==user.id,NoteSecurityMention.security_id==row["security_id"]).order_by(Note.created_at.desc())).all()
        calls=session.scalars(select(TrackedCall).join(TrackedCallLeg).where(TrackedCall.user_id==user.id,TrackedCallLeg.security_id==row["security_id"],TrackedCall.status=="open")).all()
        latest=notes[0].created_at if notes else None; latest=latest if latest and latest.tzinfo else latest.replace(tzinfo=timezone.utc) if latest else None
        days=(now-latest).days if latest else None
        theses=[note for note in notes if note.type=="thesis"]
        coverage="no_notes" if not notes else "no_thesis" if not theses else "stale" if days is not None and days>90 else "aging" if days is not None and days>45 else "current"
        result.append({**row,"latest_note_at":latest.isoformat() if latest else None,"days_since_research":days,"open_calls":len(calls),"coverage":coverage,"portfolio_review_needed":coverage in {"no_notes","no_thesis","stale"}})
    return result


@app.get("/api/tickers")
async def list_tickers(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = session.execute(
        select(Security.symbol, func.count(func.distinct(NoteSecurityMention.note_id)), func.min(Note.created_at))
        .join(NoteSecurityMention, NoteSecurityMention.security_id == Security.id)
        .join(Note, Note.id == NoteSecurityMention.note_id)
        .where(Note.user_id == user.id)
        .group_by(Security.symbol)
        .order_by(Security.symbol)
    ).all()
    open_call_counts = dict(session.execute(
        select(Security.symbol, func.count(TrackedCall.id))
        .join(TrackedCallLeg, TrackedCallLeg.security_id == Security.id)
        .join(TrackedCall, TrackedCall.id == TrackedCallLeg.tracked_call_id)
        .where(TrackedCall.user_id == user.id, TrackedCall.status == "open")
        .group_by(Security.symbol)
    ).all())
    return [{"symbol": symbol, "notes": notes, "open_calls": open_call_counts.get(symbol, 0), "first_mentioned_at": first.isoformat() if first else None} for symbol, notes, first in rows]


@app.get("/api/tickers/{symbol}")
async def ticker_detail(symbol: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    security = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not security:
        raise HTTPException(status_code=404, detail="Ticker not found")
    notes = session.scalars(select(Note).join(NoteSecurityMention, NoteSecurityMention.note_id == Note.id).where(Note.user_id == user.id, NoteSecurityMention.security_id == security.id).order_by(Note.created_at.desc())).all()
    calls = session.scalars(select(TrackedCall).join(TrackedCallLeg, TrackedCallLeg.tracked_call_id == TrackedCall.id).where(TrackedCall.user_id == user.id, TrackedCallLeg.security_id == security.id).order_by(TrackedCall.opened_at.desc())).all()
    quote = session.scalar(select(SecurityPrice).where(SecurityPrice.security_id == security.id).order_by(SecurityPrice.timestamp.desc()).limit(1))
    events = session.scalars(select(CallEvent).join(TrackedCall, TrackedCall.id == CallEvent.tracked_call_id).join(TrackedCallLeg, TrackedCallLeg.tracked_call_id == TrackedCall.id).where(TrackedCall.user_id == user.id, TrackedCallLeg.security_id == security.id).order_by(CallEvent.occurred_at.desc())).all()
    return {"symbol": security.symbol, "company_name": security.company_name, "quote": {"price": float(quote.raw_price), "timestamp": quote.timestamp.isoformat(), "basis": quote.price_type} if quote else None, "notes": [serialized_note(session, note) for note in notes], "calls": [{"call": serialize_call(session, call), "returns": call_return_object(session, call)} for call in calls], "timeline": [{"type": event.event_type, "occurred_at": event.occurred_at.isoformat(), "explanation": event.explanation, "call_id": event.tracked_call_id} for event in events]}


@app.post("/api/notes/import-legacy")
@app.post("/api/notes/sync", deprecated=True)
def import_legacy_notes(payload: SyncRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    """Explicit compatibility import; new browser writes use individual APIs."""
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
    save_thesis_details(session, note.id, payload.thesis_details)
    session.commit()
    log_event("note_published", user_id=user.id, note_id=note.id, call_count=len(parsed["tracked_calls"]))
    return serialized_note(session, note)


@app.post("/api/capture")
def capture(payload: ParseRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"]})
    note = create_note(session, user_id=user.id, parsed=parsed, title="", status="draft")
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
def backfill_legacy_entries(payload: BackfillRequest, user: CurrentUser = Depends(get_current_user)):
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


@app.post("/api/calls/{call_id}/{event_type}")
def lifecycle(call_id: str, event_type: str, payload: LifecycleRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    return execute_lifecycle(session, call_id=call_id, user_id=user.id, event_type=event_type,
        explanation=payload.explanation, idempotency_key=payload.idempotency_key,
        invalidation_category=payload.invalidation_category, body=payload.body, title=payload.title,
        provider=YFinanceMarketDataProvider(), confidence_before=payload.confidence_before, confidence_after=payload.confidence_after, thesis_state=payload.thesis_state, allow_snapshot_unavailable=payload.allow_snapshot_unavailable)

@app.get("/api/review-settings")
def review_settings(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    row=settings_for(session,user.id); session.commit()
    return {"stale_warning_days":row.stale_warning_days,"stale_critical_days":row.stale_critical_days,"absolute_move_threshold":float(row.absolute_move_threshold),"relative_move_threshold":float(row.relative_move_threshold),"daily_move_threshold":float(row.daily_move_threshold)}

@app.put("/api/review-settings")
def update_review_settings(payload: ReviewSettingsRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    if payload.stale_critical_days < payload.stale_warning_days: raise HTTPException(422,"Critical stale threshold must be at least warning threshold")
    row=settings_for(session,user.id)
    for field,value in payload.model_dump().items(): setattr(row,field,value)
    session.commit(); return review_settings(user,session)

@app.post("/api/reviews/generate")
def generate_review_queue(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    created=generate_reviews(session,user.id); session.commit(); return {"created":len(created),"reviews":[serialize_review(session,r) for r in created]}

@app.get("/api/reviews")
def list_reviews(status: str | None=None, review_type: str | None=None, ticker: str | None=None, call_id: str | None=None, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    statement=select(ThesisReview).where(ThesisReview.user_id==user.id)
    if status: statement=statement.where(ThesisReview.review_status==status)
    if review_type: statement=statement.where(ThesisReview.review_type==review_type)
    if call_id: statement=statement.where(ThesisReview.tracked_call_id==call_id)
    reviews=session.scalars(statement.order_by(ThesisReview.created_at.desc())).all()
    result=[serialize_review(session,r) for r in reviews]
    if ticker: result=[r for r in result if (r["call"] or {}).get("symbol", "").upper()==ticker.upper() or ticker.upper() in str(r["call"])]
    return result

@app.get("/api/reviews/{review_id}")
def review_detail(review_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    review=session.scalar(select(ThesisReview).where(ThesisReview.id==review_id,ThesisReview.user_id==user.id))
    if not review: raise HTTPException(404,"Review not found")
    return serialize_review(session,review)

@app.post("/api/reviews/{review_id}/complete")
def complete_review(review_id: str,payload: ReviewCompleteRequest,user: CurrentUser=Depends(get_current_user),session: Session=Depends(get_session)):
    if payload.outcome not in OUTCOMES: raise HTTPException(422,"Invalid review outcome")
    review=session.scalar(select(ThesisReview).where(ThesisReview.id==review_id,ThesisReview.user_id==user.id))
    if not review: raise HTTPException(404,"Review not found")
    if review.review_status not in {"pending","snoozed"}: raise HTTPException(409,"Review is no longer actionable")
    call=session.get(TrackedCall,review.tracked_call_id)
    review.review_status="completed"; review.completed_at=datetime.now(timezone.utc); review.outcome=payload.outcome; review.explanation=payload.explanation
    for field in ("confidence_before","confidence_after","thesis_state_before","thesis_state_after"): setattr(review,field,getattr(payload,field))
    review.snapshot_json={"returns":call_return_object(session,call),"completed_at":review.completed_at.isoformat()}
    if payload.next_review_at: session.add(ThesisReview(user_id=user.id,tracked_call_id=call.id,review_type="scheduled",scheduled_for=payload.next_review_at,metadata_json={"created_by_review":review.id}))
    session.commit(); return serialize_review(session,review)

@app.post("/api/reviews/{review_id}/snooze")
def snooze_review(review_id: str,payload: ReviewSnoozeRequest,user: CurrentUser=Depends(get_current_user),session: Session=Depends(get_session)):
    if payload.snooze_until <= datetime.now(timezone.utc): raise HTTPException(422,"Snooze date must be in the future")
    review=session.scalar(select(ThesisReview).where(ThesisReview.id==review_id,ThesisReview.user_id==user.id))
    if not review: raise HTTPException(404,"Review not found")
    review.review_status="snoozed"; review.scheduled_for=payload.snooze_until; review.explanation=payload.explanation; session.commit(); return serialize_review(session,review)

@app.post("/api/reviews/{review_id}/dismiss")
def dismiss_review(review_id: str,user: CurrentUser=Depends(get_current_user),session: Session=Depends(get_session)):
    review=session.scalar(select(ThesisReview).where(ThesisReview.id==review_id,ThesisReview.user_id==user.id))
    if not review: raise HTTPException(404,"Review not found")
    review.review_status="dismissed"; session.commit(); return serialize_review(session,review)

@app.get("/api/tickers/{symbol}/timeline")
def ticker_timeline_api(symbol: str, kind: str="all", order: str="desc", user: CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    return ticker_timeline(session,user.id,symbol,kind,order)

@app.get("/api/tickers/{symbol}/thinking-evolution")
def ticker_evolution_api(symbol: str,scope: str="all",user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    return thinking_evolution(session,user.id,symbol,scope)


@app.get("/api/export/calls.csv")
def export_calls(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    rows = ["Call,Type,Status,Opened,Entry,Current"]
    for call in session.scalars(select(TrackedCall).where(TrackedCall.user_id == user.id).order_by(TrackedCall.opened_at.desc())).all():
        payload = serialize_call(session, call)
        symbol = payload.get("symbol") or f"{payload['long']['symbol']}/{payload['short']['symbol']}"
        entry = payload.get("entry") or payload.get("long", {}).get("entry", "")
        current = payload.get("current") or payload.get("long", {}).get("current", "")
        rows.append(f"{symbol},{payload['type']},{payload['status']},{payload['opened']},{entry},{current}")
    return "\n".join(rows)


web_root = Path(__file__).parents[2]


@app.get("/notes/{note_id}")
@app.get("/calls/{call_id}")
@app.get("/tickers/{symbol}")
@app.get("/settings")
@app.get("/portfolio")
@app.get("/review")
@app.get("/login")
def journal_route():
    """Serve the client shell for bookmarkable Phase 2 journal routes."""
    return FileResponse(web_root / "index.html")


app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
