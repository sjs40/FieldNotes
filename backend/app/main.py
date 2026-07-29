from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from .database import Base, engine, get_session
from .config import settings
from .models import Assumption, AssumptionEvent, BrokerageAccount, BrokerageConnection, CallBenchmarkSnapshot, CallEvent, CallExpectation, CompanyWorkspace, EmailConnection, Evidence, EvidenceAssumption, EvidenceForecast, EvidenceQuestion, EvidenceThesis, Forecast, ForecastEvent, Idea, IdeaSecurity, InboxItem, MetricCard, Note, NoteRelationship, NoteRevision, NoteSecurityMention, NoteSource, NoteTag, PortfolioPosition, QuestionEvent, ResearchQuestion, SavedView, Source, SourceSecurityMention, SourceTag, Security, SecurityPrice, Tag, ThesisDetails, ThesisReview, ThinkingUpdate, TrackedCall, TrackedCallLeg, UserReviewSettings, UserWorkspacePreference, WeeklyReview
from .parser import capture_title, parse_note
from .market_data import YFinanceMarketDataProvider
from .auth import CurrentUser, get_current_user
from .journal import call_return_object, create_note, replace_note_relationships, serialize_call, serialize_note as serialize_journal_note
from .lifecycle import execute as execute_lifecycle
from .observability import RequestObservabilityMiddleware, init_sentry, log_event
from hashlib import sha256
import secrets
from .reviews import OUTCOMES, REVIEW_TYPES, STATUSES, generate as generate_reviews, serialize_review, settings_for
from .timeline import thinking_evolution, ticker_timeline
from .inbox import capture as inbox_capture, clean_html, normalize_url

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
    source_url: str | None = None
    active_ticker: str | None = Field(default=None, max_length=32)
    thesis_details: dict | None = None
    pending_questions: list[dict] = []


class EditNoteRequest(BaseModel):
    body: str
    note_type: str = "note"
    title: str = ""


class CompanyWorkspaceRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    company_name: str | None = Field(default=None, max_length=255)
    company_description: str | None = Field(default=None, max_length=20000)
    business_model: str | None = Field(default=None, max_length=20000)
    is_followed: bool = True


class CompanyWorkspaceUpdateRequest(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    company_description: str | None = Field(default=None, max_length=20000)
    business_model: str | None = Field(default=None, max_length=20000)
    is_followed: bool | None = None

class FollowUpRequest(PublishRequest):
    relationship_type: str = "updates"
    explanation: str | None = None
    thinking_update: dict | None = None

class LedgerRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=10000)
    ticker: str | None = None
    status: str | None = None
    importance: str | None = None
    direction: str | None = None
    strength: str | None = None
    source_id: str | None = None
    assumption_ids: list[str] = []
    thesis_note_ids: list[str] = []
    forecast_ids: list[str] = []
    question_ids: list[str] = []
    note_id: str | None = None
    priority: str | None = None
    due_at: datetime | None = None

class ForecastRequest(BaseModel):
    metric_name: str = Field(min_length=1, max_length=255)
    ticker: str | None = None
    forecast_type: str = "point"
    target_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    value_unit: str | None = None
    direction: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    target_period_start: datetime
    target_period_end: datetime | None = None
    note_id: str | None = None
    assumption_id: str | None = None

class ForecastResolutionRequest(BaseModel):
    resolution_value: float | None = None
    outcome: str
    resolution_source_id: str | None = None
    resolution_note: str | None = None

class UpdateAssumptionRequest(BaseModel):
    status: str | None = None
    importance: str | None = None
    current_value: str | None = None
    explanation: str | None = None

class AnswerQuestionRequest(BaseModel):
    status: str = "answered"
    answer_summary: str | None = None
    answered_by_note_id: str | None = None
    answered_by_source_id: str | None = None

class ConvertRequest(BaseModel):
    target_type: str
    title: str = ""
    body: str | None = None
    statement: str | None = None
    ticker: str | None = None
    priority: str = "medium"

class ChallengeRequest(BaseModel):
    title: str = "Challenge thesis"
    opposing_case: str | None = None
    weakest_assumption: str | None = None
    discounted_evidence: str | None = None
    market_knows: str | None = None
    delayed_catalyst: str | None = None
    fundamental_vs_stock: str | None = None
    ticker: str | None = None
    assumption_ids: list[str] = []
    evidence_ids: list[str] = []

class SavedViewRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    resource: str = Field(pattern="^(notes|questions|forecasts|tickers)$")
    filters: dict = {}
    sort: dict = {}
    columns: dict = {}
    is_default: bool = False
    is_pinned: bool = False

class MetricCardRequest(BaseModel):
    metric_name:str=Field(min_length=1,max_length=255); value:float; period:str=Field(min_length=1,max_length=128); ticker:str|None=None; value_unit:str|None=None; prior_value:float|None=None; consensus_value:float|None=None; note_id:str|None=None; source_id:str|None=None; forecast_id:str|None=None; interpretation:str|None=None; data:dict={}
class IdeaRequest(BaseModel):
    title:str=Field(min_length=1,max_length=500); description:str|None=None; stage:str="spark"; priority:str="medium"; ticker_symbols:list[str]=[]; originating_note_id:str|None=None; source_id:str|None=None; why_it_matters:str|None=None; why_now:str|None=None; next_step:str|None=None; rejection_reason:str|None=None
class WeeklyReviewRequest(BaseModel):
    week_start:datetime|None=None; conclusions:dict={}; complete:bool=False
class TableParseRequest(BaseModel):
    text:str=Field(min_length=1,max_length=50000)
class ChartRequest(BaseModel):
    metric_card_id:str; chart_type:str="line"


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
    user_id: str | None = None
    connection_name: str = "Interactive Brokers"
    account_id: str
    account_type: str | None = None
    base_currency: str = "USD"
    snapshot_at: datetime
    positions: list[dict]
class IBKRConnectionRequest(BaseModel):
    display_name:str="Interactive Brokers"; host:str="127.0.0.1"; port:int=7497; client_id:int=17
class CaptureRequest(BaseModel):
    channel:str="web"; external_id:str|None=None; idempotency_key:str|None=None; item_type:str="text"; title:str=""; text:str=""; url:str|None=None; received_at:datetime|None=None; metadata:dict={}
class SourceRequest(BaseModel):
    source_type:str="manual"; external_id:str|None=None; url:str|None=None; title:str=""; content:str=""; metadata:dict={}
class InboxPatchRequest(BaseModel):
    status:str|None=None; title:str|None=None; text:str|None=None; tags:list[str]|None=None; tickers:list[str]|None=None
class SourceLinkRequest(BaseModel):
    note_id:str; relationship_type:str="references"; excerpt:str|None=None
class BulkInboxRequest(BaseModel):
    item_ids:list[str]; action:str; tag:str|None=None; ticker:str|None=None

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
    relations=session.scalars(select(NoteRelationship).where(or_(NoteRelationship.from_note_id==note.id,NoteRelationship.to_note_id==note.id))).all()
    outgoing=[r for r in relations if r.from_note_id==note.id]; incoming=[r for r in relations if r.to_note_id==note.id]
    result["relationship_summary"]={"follow_up_count":len(incoming),"supporting_count":sum(r.relationship_type=="supports" for r in relations),"contradiction_count":sum(r.relationship_type=="contradicts" for r in relations),"superseded_by":next((r.from_note_id for r in incoming if r.relationship_type=="supersedes"),None)}
    result["open_question_count"]=session.scalar(select(func.count(ResearchQuestion.id)).where(ResearchQuestion.originating_note_id==note.id,ResearchQuestion.status.in_(("open","partially_answered")))) or 0
    result["evidence_count"]=session.scalar(select(func.count(Evidence.id)).where(Evidence.originating_note_id==note.id)) or 0
    sources = session.execute(
        select(Source.id, Source.title, Source.canonical_url)
        .join(NoteSource, NoteSource.source_id == Source.id)
        .where(NoteSource.note_id == note.id)
        .order_by(NoteSource.created_at.asc())
    ).all()
    result["sources"] = [{"id": source_id, "title": title, "url": url} for source_id, title, url in sources]
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


def link_note_source_url(session: Session, user_id: str, note: Note, source_url: str | None) -> None:
    """Link an optional article URL without creating an Inbox item or fetching it."""
    if not source_url or not source_url.strip():
        return
    original_url = source_url.strip()
    parts = urlsplit(original_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise HTTPException(status_code=422, detail="Source URL must be a valid http(s) URL")
    canonical_url = normalize_url(original_url)
    source = session.scalar(select(Source).where(Source.user_id == user_id, Source.canonical_url == canonical_url))
    if source is None:
        source = Source(
            user_id=user_id,
            source_type="article",
            canonical_url=canonical_url,
            original_url=original_url,
            title=note.title or None,
            content_status="partial",
        )
        session.add(source)
        session.flush()
    if session.get(NoteSource, {"note_id": note.id, "source_id": source.id}) is None:
        session.add(NoteSource(note_id=note.id, source_id=source.id, relationship_type="references"))


def _company_workspace(session: Session, user_id: str, symbol: str, *, create: bool = False) -> tuple[CompanyWorkspace | None, Security | None]:
    security = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if security is None and create:
        security = Security(symbol=symbol.upper())
        session.add(security)
        session.flush()
    if security is None:
        return None, None
    workspace = session.scalar(select(CompanyWorkspace).where(CompanyWorkspace.user_id == user_id, CompanyWorkspace.security_id == security.id))
    if workspace is None and create:
        workspace = CompanyWorkspace(user_id=user_id, security_id=security.id)
        session.add(workspace)
        session.flush()
    return workspace, security


def _workspace_payload(session: Session, workspace: CompanyWorkspace, security: Security, active_security_id: str | None = None) -> dict:
    note_count = session.scalar(select(func.count(NoteSecurityMention.note_id)).join(Note, Note.id == NoteSecurityMention.note_id).where(Note.user_id == workspace.user_id, NoteSecurityMention.security_id == security.id)) or 0
    return {"symbol": security.symbol, "company_name": security.company_name, "company_description": workspace.company_description, "business_model": workspace.business_model, "is_followed": workspace.is_followed, "is_active": security.id == active_security_id, "note_count": note_count, "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None}


def _scope_parsed_to_active_company(session: Session, user_id: str, parsed: dict, active_ticker: str | None) -> dict:
    """Apply UI company context only when the capture contains no explicit ticker."""
    if not active_ticker or parsed["ticker_mentions"]:
        return parsed
    workspace, security = _company_workspace(session, user_id, active_ticker)
    if workspace is None or security is None:
        raise HTTPException(status_code=422, detail="Choose a company workspace before using it for capture context")
    return {**parsed, "ticker_mentions": [security.symbol]}


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
    # PostgreSQL cannot apply DISTINCT to the JSON metadata column on Note.
    # De-duplicate lightweight IDs instead, then hydrate the requested notes.
    note_ids = session.execute(
        statement.with_only_columns(Note.id, order)
        .distinct()
        .order_by(order)
        .offset(max(0, offset))
        .limit(min(max(1, limit), 200))
    ).all()
    notes = [session.get(Note, note_id) for note_id, _ in note_ids]
    return [serialized_note(session, note) for note in notes]


@app.post("/api/notes")
async def create_draft(payload: PublishRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"]:
        raise HTTPException(status_code=422, detail={"errors": parsed["errors"]})
    parsed = _scope_parsed_to_active_company(session, user.id, parsed, payload.active_ticker)
    note = create_note(session, user_id=user.id, parsed=parsed, title=payload.title or capture_title(payload.body, parsed), status="draft")
    link_note_source_url(session, user.id, note, payload.source_url)
    save_thesis_details(session, note.id, payload.thesis_details)
    _create_pending_questions(session, user.id, note, payload.pending_questions)
    session.commit()
    return serialized_note(session, note)


@app.get("/api/notes/search")
async def search_notes(q: str = "", limit: int = 100, offset: int = 0, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    query = q.strip()
    if not query:
        return []
    pattern = f"%{query}%"
    note_ids = session.execute(
        select(Note.id, Note.created_at).outerjoin(NoteTag, NoteTag.note_id == Note.id).outerjoin(Tag, Tag.id == NoteTag.tag_id).outerjoin(NoteSecurityMention, NoteSecurityMention.note_id == Note.id).outerjoin(Security, Security.id == NoteSecurityMention.security_id).outerjoin(CallEvent, CallEvent.note_id == Note.id).where(
            Note.user_id == user.id,
            or_(Note.title.ilike(pattern), Note.body.ilike(pattern), Tag.display_name.ilike(pattern), Security.symbol.ilike(pattern), Security.company_name.ilike(pattern), CallEvent.explanation.ilike(pattern)),
        ).distinct().order_by(Note.created_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 200))
    ).all()
    notes = [session.get(Note, note_id) for note_id, _ in note_ids]
    return [serialized_note(session, note) for note in notes]


@app.get("/api/notes/{note_id}/revisions")
async def list_revisions(note_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    note = session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    revisions = session.scalars(select(NoteRevision).where(NoteRevision.note_id == note.id).order_by(NoteRevision.revision_number.desc())).all()
    return [{"id": revision.id, "revision_number": revision.revision_number, "title": revision.title or "", "body": revision.body, "type": revision.type, "edited_at": revision.edited_at.isoformat()} for revision in revisions]

@app.get("/api/notes/{note_id}/deltas")
def note_deltas(note_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    import difflib
    note=_owned_note(session,note_id,user.id)
    revisions=session.scalars(select(NoteRevision).where(NoteRevision.note_id==note.id).order_by(NoteRevision.revision_number)).all()
    deltas=[]
    for before,after in zip(revisions,revisions[1:]):
        diff=list(difflib.ndiff((before.body or "").splitlines(),(after.body or "").splitlines()))
        added=[line[2:] for line in diff if line.startswith("+ ")];removed=[line[2:] for line in diff if line.startswith("- ")]
        summary=[]
        if added:summary.append(f"{len(added)} line(s) added.")
        if removed:summary.append(f"{len(removed)} line(s) removed.")
        if before.title!=after.title:summary.append("Title changed.")
        deltas.append({"from_revision":before.revision_number,"to_revision":after.revision_number,"added":added,"removed":removed,"summary":summary,"at":after.edited_at.isoformat()})
    updates=session.scalars(select(ThinkingUpdate).where(ThinkingUpdate.update_note_id==note.id,ThinkingUpdate.user_id==user.id).order_by(ThinkingUpdate.created_at)).all()
    for update in updates:
        summary=[]
        if update.target_before is not None and update.target_after is not None:summary.append(f"Target changed from {float(update.target_before):g} to {float(update.target_after):g}.")
        if update.confidence_before!=update.confidence_after and update.confidence_after:summary.append(f"Confidence changed from {update.confidence_before or 'unspecified'} to {update.confidence_after}.")
        if update.thesis_state_before!=update.thesis_state_after and update.thesis_state_after:summary.append(f"Thesis state changed to {update.thesis_state_after}.")
        deltas.append({"thinking_update_id":update.id,"summary":summary,"reason":update.change_reason,"at":update.created_at.isoformat()})
    return deltas


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


RELATIONSHIP_TYPES = {"update_of", "updates", "supports", "contradicts", "answers", "derived_from", "supersedes", "related", "challenge_to", "converts_to"}

def _owned_note(session, note_id, user_id):
    note = session.scalar(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    if not note: raise HTTPException(404, "Note not found")
    return note

def _security_for_ticker(session, ticker):
    return session.scalar(select(Security).where(Security.symbol == ticker.upper())) if ticker else None

def _create_pending_questions(session, user_id, note, pending):
    for item in pending:
        text = (item.get("question") or "").strip()
        if not text: continue
        security = _security_for_ticker(session, item.get("ticker"))
        session.add(ResearchQuestion(user_id=user_id, security_id=security.id if security else None, originating_note_id=note.id, thesis_note_id=note.id if note.type == "thesis" else None, question=text, priority=item.get("priority", "medium"), due_at=item.get("due_at")))

@app.get("/api/notes/{note_id}/relationships")
def note_relationships(note_id: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    note = _owned_note(session, note_id, user.id)
    rows = session.scalars(select(NoteRelationship).where(or_(NoteRelationship.from_note_id == note.id, NoteRelationship.to_note_id == note.id)).order_by(NoteRelationship.created_at.desc())).all()
    result=[]
    for row in rows:
        other_id = row.to_note_id if row.from_note_id == note.id else row.from_note_id
        other = session.scalar(select(Note).where(Note.id == other_id, Note.user_id == user.id))
        if other: result.append({"id":row.id,"direction":"outgoing" if row.from_note_id == note.id else "incoming","relationship_type":row.relationship_type,"explanation":row.explanation,"note":{"id":other.id,"title":other.title or other.body[:160],"type":other.type},"created_at":row.created_at.isoformat()})
    return result

@app.post("/api/notes/{note_id}/follow-ups")
def add_follow_up(note_id: str, payload: FollowUpRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    parent = _owned_note(session, note_id, user.id)
    if payload.relationship_type not in RELATIONSHIP_TYPES: raise HTTPException(422, "Invalid relationship type")
    parsed = parse_note(payload.body, payload.note_type)
    if parsed["errors"] or parsed["warnings"]: raise HTTPException(422, detail={"errors":parsed["errors"],"warnings":parsed["warnings"]})
    # Follow-ups are notes, never implicit tracked calls; explicit call creation stays in its established workflow.
    if parsed["tracked_calls"]: raise HTTPException(422, "Follow-ups cannot implicitly open tracked calls")
    child = create_note(session, user_id=user.id, parsed=parsed, title=payload.title, status="published", quotes={})
    session.add(NoteRelationship(user_id=user.id, from_note_id=child.id, to_note_id=parent.id, relationship_type=payload.relationship_type, explanation=payload.explanation, created_by_workflow="follow_up"))
    _create_pending_questions(session, user.id, child, payload.pending_questions)
    if payload.thinking_update:
        data = payload.thinking_update
        security = _security_for_ticker(session, data.get("ticker"))
        session.add(ThinkingUpdate(user_id=user.id, security_id=security.id if security else None, update_note_id=child.id, prior_note_id=parent.id, change_direction=data.get("change_direction", "unchanged"), confidence_before=data.get("confidence_before"), confidence_after=data.get("confidence_after"), target_before=data.get("target_before"), target_after=data.get("target_after"), target_unit=data.get("target_unit"), horizon_before_days=data.get("horizon_before_days"), horizon_after_days=data.get("horizon_after_days"), change_reason=data.get("change_reason")))
    session.commit(); return serialized_note(session, child)

@app.post("/api/assumptions")
def create_assumption(payload: LedgerRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    security=_security_for_ticker(session,payload.ticker)
    if payload.note_id: _owned_note(session,payload.note_id,user.id)
    status_value=payload.status or "untested"; importance=payload.importance or "medium"
    if status_value not in {"untested","supported","challenged","confirmed","disproven","retired"} or importance not in {"low","medium","high","critical"}: raise HTTPException(422,"Invalid assumption state")
    value=Assumption(user_id=user.id,security_id=security.id if security else None,originating_note_id=payload.note_id,statement=payload.statement,status=status_value,importance=importance)
    session.add(value);session.flush();session.add(AssumptionEvent(assumption_id=value.id,user_id=user.id,event_type="created",to_value=status_value));session.commit();return {"id":value.id,"statement":value.statement,"status":value.status,"importance":value.importance}

@app.get("/api/assumptions")
def list_assumptions(ticker:str|None=None,status_value:str|None=None,limit:int=100,offset:int=0,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(Assumption).where(Assumption.user_id==user.id)
    if ticker:
        security=_security_for_ticker(session,ticker); q=q.where(Assumption.security_id==security.id) if security else q.where(False)
    if status_value:q=q.where(Assumption.status==status_value)
    rows=session.scalars(q.order_by(Assumption.updated_at.desc()).offset(max(offset,0)).limit(min(max(limit,1),200))).all()
    return [{"id":x.id,"statement":x.statement,"status":x.status,"importance":x.importance,"security_id":x.security_id,"updated_at":x.updated_at.isoformat()} for x in rows]

@app.post("/api/evidence")
def create_evidence(payload: LedgerRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    security=_security_for_ticker(session,payload.ticker)
    if payload.note_id:_owned_note(session,payload.note_id,user.id)
    if payload.source_id and not session.scalar(select(Source).where(Source.id==payload.source_id,Source.user_id==user.id)):raise HTTPException(404,"Source not found")
    direction=payload.direction or "contextual"; strength=payload.strength or "moderate"
    if direction not in {"supports","contradicts","mixed","contextual"} or strength not in {"weak","moderate","strong"}:raise HTTPException(422,"Invalid evidence classification")
    value=Evidence(user_id=user.id,security_id=security.id if security else None,originating_note_id=payload.note_id,source_id=payload.source_id,statement=payload.statement,evidence_direction=direction,strength=strength)
    session.add(value);session.flush()
    for aid in set(payload.assumption_ids):
        if not session.scalar(select(Assumption).where(Assumption.id==aid,Assumption.user_id==user.id)):raise HTTPException(404,"Assumption not found")
        session.add(EvidenceAssumption(evidence_id=value.id,assumption_id=aid))
    for nid in set(payload.thesis_note_ids):
        thesis=_owned_note(session,nid,user.id)
        if thesis.type!="thesis":raise HTTPException(422,"Evidence thesis links require a thesis note")
        session.add(EvidenceThesis(evidence_id=value.id,thesis_note_id=nid))
    for fid in set(payload.forecast_ids):
        if not session.scalar(select(Forecast).where(Forecast.id==fid,Forecast.user_id==user.id)):raise HTTPException(404,"Forecast not found")
        session.add(EvidenceForecast(evidence_id=value.id,forecast_id=fid))
    for qid in set(payload.question_ids):
        if not session.scalar(select(ResearchQuestion).where(ResearchQuestion.id==qid,ResearchQuestion.user_id==user.id)):raise HTTPException(404,"Question not found")
        session.add(EvidenceQuestion(evidence_id=value.id,question_id=qid))
    session.commit();return {"id":value.id,"statement":value.statement,"direction":value.evidence_direction}

@app.post("/api/questions")
def create_question(payload:LedgerRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    security=_security_for_ticker(session,payload.ticker)
    if payload.note_id:_owned_note(session,payload.note_id,user.id)
    priority=payload.priority or "medium"
    if priority not in {"low","medium","high","critical"}:raise HTTPException(422,"Invalid question priority")
    value=ResearchQuestion(user_id=user.id,security_id=security.id if security else None,originating_note_id=payload.note_id,question=payload.statement,priority=priority,due_at=payload.due_at);session.add(value);session.commit();return {"id":value.id,"question":value.question,"status":value.status}

@app.get("/api/questions")
def research_queue(ticker:str|None=None,status_value:str|None=None,limit:int=100,offset:int=0,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(ResearchQuestion).where(ResearchQuestion.user_id==user.id)
    if ticker:
        security=_security_for_ticker(session,ticker);q=q.where(ResearchQuestion.security_id==security.id) if security else q.where(False)
    if status_value:q=q.where(ResearchQuestion.status==status_value)
    rows=session.scalars(q.order_by(ResearchQuestion.priority.desc(),ResearchQuestion.due_at.asc().nulls_last(),ResearchQuestion.created_at.asc()).offset(max(offset,0)).limit(min(max(limit,1),200))).all()
    return [{"id":x.id,"question":x.question,"status":x.status,"priority":x.priority,"due_at":x.due_at.isoformat() if x.due_at else None,"security_id":x.security_id} for x in rows]

@app.post("/api/forecasts")
def create_forecast(payload:ForecastRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    security=_security_for_ticker(session,payload.ticker)
    if payload.note_id:_owned_note(session,payload.note_id,user.id)
    if payload.assumption_id and not session.scalar(select(Assumption).where(Assumption.id==payload.assumption_id,Assumption.user_id==user.id)):raise HTTPException(404,"Assumption not found")
    if payload.forecast_type not in {"point","minimum","maximum","range","direction","event","probability"}:raise HTTPException(422,"Invalid forecast type")
    if payload.target_period_end and payload.target_period_end < payload.target_period_start:raise HTTPException(422,"Forecast period end must follow start")
    value=Forecast(user_id=user.id,security_id=security.id if security else None,originating_note_id=payload.note_id,assumption_id=payload.assumption_id,metric_name=payload.metric_name,forecast_type=payload.forecast_type,target_value=payload.target_value,lower_bound=payload.lower_bound,upper_bound=payload.upper_bound,value_unit=payload.value_unit,direction=payload.direction,probability=payload.probability,target_period_start=payload.target_period_start,target_period_end=payload.target_period_end);session.add(value);session.commit();return {"id":value.id,"metric_name":value.metric_name,"status":value.status}

@app.post("/api/forecasts/{forecast_id}/resolve")
def resolve_forecast(forecast_id:str,payload:ForecastResolutionRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    value=session.scalar(select(Forecast).where(Forecast.id==forecast_id,Forecast.user_id==user.id))
    if not value:raise HTTPException(404,"Forecast not found")
    if value.status!="open":raise HTTPException(409,"Forecast is already resolved")
    if payload.outcome not in {"correct","partially_correct","incorrect","unresolvable"}:raise HTTPException(422,"Invalid forecast outcome")
    if payload.resolution_source_id and not session.scalar(select(Source).where(Source.id==payload.resolution_source_id,Source.user_id==user.id)):raise HTTPException(404,"Source not found")
    value.status="resolved";value.outcome=payload.outcome;value.resolution_value=payload.resolution_value;value.resolution_source_id=payload.resolution_source_id;value.resolution_note=payload.resolution_note;value.resolved_at=datetime.now(timezone.utc)
    if value.target_value is not None and payload.resolution_value is not None:
        value.error_value=float(payload.resolution_value)-float(value.target_value);value.error_percentage=value.error_value/abs(float(value.target_value)) if value.target_value else None
    session.add(ForecastEvent(forecast_id=value.id,user_id=user.id,event_type="resolved",snapshot_json={"resolution_value":payload.resolution_value,"outcome":payload.outcome,"error_value":float(value.error_value) if value.error_value is not None else None},explanation=payload.resolution_note))
    session.commit();return {"id":value.id,"status":value.status,"outcome":value.outcome,"error_value":float(value.error_value) if value.error_value is not None else None}

@app.patch("/api/assumptions/{assumption_id}")
def update_assumption(assumption_id:str,payload:UpdateAssumptionRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    value=session.scalar(select(Assumption).where(Assumption.id==assumption_id,Assumption.user_id==user.id))
    if not value: raise HTTPException(404,"Assumption not found")
    previous={"status":value.status,"importance":value.importance,"current_value":value.current_value}
    if payload.status is not None:
        if payload.status not in {"untested","supported","challenged","confirmed","disproven","retired"}:raise HTTPException(422,"Invalid assumption state")
        value.status=payload.status
        if payload.status in {"confirmed","disproven","retired"}:value.resolved_at=datetime.now(timezone.utc)
    if payload.importance is not None:
        if payload.importance not in {"low","medium","high","critical"}:raise HTTPException(422,"Invalid importance")
        value.importance=payload.importance
    if payload.current_value is not None:value.current_value=payload.current_value
    for field,old in previous.items():
        new=getattr(value,field)
        if old!=new:session.add(AssumptionEvent(assumption_id=value.id,user_id=user.id,event_type=field+"_changed",from_value=str(old) if old is not None else None,to_value=str(new) if new is not None else None,explanation=payload.explanation))
    session.commit();return {"id":value.id,"status":value.status,"importance":value.importance,"current_value":value.current_value}

@app.get("/api/assumptions/{assumption_id}/events")
def assumption_events(assumption_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    value=session.scalar(select(Assumption).where(Assumption.id==assumption_id,Assumption.user_id==user.id))
    if not value:raise HTTPException(404,"Assumption not found")
    rows=session.scalars(select(AssumptionEvent).where(AssumptionEvent.assumption_id==value.id,AssumptionEvent.user_id==user.id).order_by(AssumptionEvent.created_at.desc())).all()
    return [{"type":x.event_type,"from":x.from_value,"to":x.to_value,"explanation":x.explanation,"at":x.created_at.isoformat()} for x in rows]

@app.post("/api/questions/{question_id}/answer")
def answer_question(question_id:str,payload:AnswerQuestionRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    value=session.scalar(select(ResearchQuestion).where(ResearchQuestion.id==question_id,ResearchQuestion.user_id==user.id))
    if not value:raise HTTPException(404,"Question not found")
    if payload.status not in {"open","partially_answered","answered","no_longer_relevant"}:raise HTTPException(422,"Invalid question state")
    if payload.answered_by_note_id:_owned_note(session,payload.answered_by_note_id,user.id)
    if payload.answered_by_source_id and not session.scalar(select(Source).where(Source.id==payload.answered_by_source_id,Source.user_id==user.id)):raise HTTPException(404,"Source not found")
    old=value.status;value.status=payload.status;value.answer_summary=payload.answer_summary;value.answered_by_note_id=payload.answered_by_note_id;value.answered_by_source_id=payload.answered_by_source_id
    if payload.status in {"answered","no_longer_relevant"}:value.resolved_at=datetime.now(timezone.utc)
    session.add(QuestionEvent(question_id=value.id,user_id=user.id,event_type="status_changed",from_value=old,to_value=value.status,explanation=payload.answer_summary));session.commit();return {"id":value.id,"status":value.status}

@app.get("/api/questions/{question_id}/events")
def question_events(question_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    value=session.scalar(select(ResearchQuestion).where(ResearchQuestion.id==question_id,ResearchQuestion.user_id==user.id))
    if not value:raise HTTPException(404,"Question not found")
    rows=session.scalars(select(QuestionEvent).where(QuestionEvent.question_id==value.id,QuestionEvent.user_id==user.id).order_by(QuestionEvent.created_at.desc())).all()
    return [{"type":x.event_type,"from":x.from_value,"to":x.to_value,"explanation":x.explanation,"at":x.created_at.isoformat()} for x in rows]

@app.post("/api/notes/{note_id}/convert")
def convert_note(note_id:str,payload:ConvertRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    source=_owned_note(session,note_id,user.id); target=payload.target_type
    if target not in {"question","evidence","assumption","idea","thesis"}:raise HTTPException(422,"Invalid conversion target")
    tickers=session.scalars(select(Security.symbol).join(NoteSecurityMention,NoteSecurityMention.security_id==Security.id).where(NoteSecurityMention.note_id==source.id)).all(); ticker=payload.ticker or (tickers[0] if tickers else None)
    if target in {"idea","thesis"}:
        parsed=parse_note(payload.body or source.body,target)
        if parsed["errors"] or parsed["tracked_calls"]:raise HTTPException(422,"Conversion cannot create a tracked call")
        created=create_note(session,user_id=user.id,parsed=parsed,title=payload.title or source.title or "",status="published",quotes={})
        session.add(NoteRelationship(user_id=user.id,from_note_id=source.id,to_note_id=created.id,relationship_type="converts_to",created_by_workflow="conversion"));session.commit();return {"kind":"note","note":serialized_note(session,created)}
    statement=payload.statement or payload.body or source.body
    parsed=parse_note(("$"+ticker+" " if ticker else "")+statement,target)
    created_note=create_note(session,user_id=user.id,parsed=parsed,title=payload.title or source.title or "",status="published",quotes={})
    security=_security_for_ticker(session,ticker)
    if target=="question":
        created=ResearchQuestion(user_id=user.id,security_id=security.id if security else None,originating_note_id=created_note.id,question=statement,priority=payload.priority)
    elif target=="evidence":created=Evidence(user_id=user.id,security_id=security.id if security else None,originating_note_id=created_note.id,statement=statement,evidence_direction="contextual")
    else:created=Assumption(user_id=user.id,security_id=security.id if security else None,originating_note_id=created_note.id,statement=statement)
    session.add(created);session.add(NoteRelationship(user_id=user.id,from_note_id=created_note.id,to_note_id=source.id,relationship_type="converts_to",created_by_workflow="conversion"))
    session.commit();return {"kind":target,"id":created.id,"note":serialized_note(session,created_note)}

@app.post("/api/notes/{note_id}/challenge")
def challenge_thesis(note_id:str,payload:ChallengeRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    thesis=_owned_note(session,note_id,user.id)
    if thesis.type!="thesis":raise HTTPException(422,"Only thesis notes can be challenged")
    prompts=[("Opposing case",payload.opposing_case),("Least defensible assumption",payload.weakest_assumption),("Discounted evidence",payload.discounted_evidence),("What the market may understand",payload.market_knows),("If the catalyst takes twice as long",payload.delayed_catalyst),("Fundamentals right, stock wrong",payload.fundamental_vs_stock)]
    body="\n\n".join(f"{label}: {value}" for label,value in prompts if value and value.strip())
    if not body:raise HTTPException(422,"Add at least one challenge prompt")
    tickers=session.scalars(select(Security.symbol).join(NoteSecurityMention,NoteSecurityMention.security_id==Security.id).where(NoteSecurityMention.note_id==thesis.id)).all()
    prefix="$"+(payload.ticker or (tickers[0] if tickers else "")) if payload.ticker or tickers else ""
    parsed=parse_note((prefix+" "+body).strip(),"challenge")
    note=create_note(session,user_id=user.id,parsed=parsed,title=payload.title,status="published",quotes={})
    session.add(NoteRelationship(user_id=user.id,from_note_id=note.id,to_note_id=thesis.id,relationship_type="challenge_to",created_by_workflow="challenge"))
    for aid in set(payload.assumption_ids):
        assumption=session.scalar(select(Assumption).where(Assumption.id==aid,Assumption.user_id==user.id))
        if not assumption:raise HTTPException(404,"Assumption not found")
        session.add(AssumptionEvent(assumption_id=aid,user_id=user.id,event_type="challenged_by_note",to_value=note.id,explanation=payload.weakest_assumption))
    for eid in set(payload.evidence_ids):
        if not session.scalar(select(Evidence).where(Evidence.id==eid,Evidence.user_id==user.id)):raise HTTPException(404,"Evidence not found")
        session.add(EvidenceThesis(evidence_id=eid,thesis_note_id=thesis.id))
    session.commit();return serialized_note(session,note)

def _validate_view_filters(resource,filters):
    allowed={"notes":{"ticker","tag","note_type","status","relationship_type","has_unresolved_questions","date_from","date_to"},"questions":{"ticker","status","priority","due_before"},"forecasts":{"ticker","status","target_before"},"ideas":{"stage","priority","ticker"}}
    if resource not in allowed or not isinstance(filters,dict):raise HTTPException(422,"Invalid saved view")
    if "and" in filters or "or" in filters:
        branches=filters.get("and",filters.get("or"));
        if not isinstance(branches,list) or not branches:raise HTTPException(422,"Filter groups require a non-empty list")
        for branch in branches:_validate_view_filters(resource,branch)
        return
    unknown=set(filters)-allowed[resource]
    if unknown:raise HTTPException(422,detail={"message":"Unsupported filter fields","fields":sorted(unknown)})

@app.post("/api/saved-views")
def save_view(payload:SavedViewRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    _validate_view_filters(payload.resource,payload.filters)
    value=SavedView(user_id=user.id,name=payload.name,resource=payload.resource,filters_json=payload.filters,sort_json=payload.sort,columns_json=payload.columns,is_default=payload.is_default,is_pinned=payload.is_pinned);session.add(value)
    try:session.commit()
    except Exception:
        session.rollback();raise HTTPException(409,"A saved view with that name already exists")
    return {"id":value.id,"name":value.name,"resource":value.resource,"filters":value.filters_json,"sort":value.sort_json,"pinned":value.is_pinned}

@app.get("/api/saved-views")
def saved_views(resource:str|None=None,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(SavedView).where(SavedView.user_id==user.id)
    if resource:q=q.where(SavedView.resource==resource)
    rows=session.scalars(q.order_by(SavedView.updated_at.desc())).all()
    return [{"id":x.id,"name":x.name,"resource":x.resource,"filters":x.filters_json,"sort":x.sort_json,"pinned":x.is_pinned} for x in rows]

@app.get("/api/saved-views/{view_id}/results")
def saved_view_results(view_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    view=session.scalar(select(SavedView).where(SavedView.id==view_id,SavedView.user_id==user.id))
    if not view:raise HTTPException(404,"Saved view not found")
    f=view.filters_json or {}
    def groups(value, predicate):
        if "and" in value:return and_(*[groups(x,predicate) for x in value["and"]])
        if "or" in value:return or_(*[groups(x,predicate) for x in value["or"]])
        return predicate(value)
    if view.resource=="questions":
        q=select(ResearchQuestion).where(ResearchQuestion.user_id==user.id)
        def question_pred(x):
            terms=[]
            if x.get("status"):terms.append(ResearchQuestion.status==x["status"])
            if x.get("priority"):terms.append(ResearchQuestion.priority==x["priority"])
            if x.get("ticker"):
                s=_security_for_ticker(session,x["ticker"]);terms.append(ResearchQuestion.security_id==s.id if s else False)
            return and_(*terms) if terms else True
        q=q.where(groups(f,question_pred))
        return [{"id":x.id,"question":x.question,"status":x.status,"priority":x.priority} for x in session.scalars(q).all()]
    if view.resource=="forecasts":
        q=select(Forecast).where(Forecast.user_id==user.id)
        q=q.where(groups(f,lambda x: Forecast.status==x["status"] if x.get("status") else True))
        return [{"id":x.id,"metric_name":x.metric_name,"status":x.status} for x in session.scalars(q).all()]
    if view.resource=="ideas":
        q=select(Idea).where(Idea.user_id==user.id)
        q=q.where(groups(f,lambda x: and_(*(z for z in [Idea.stage==x["stage"] if x.get("stage") else True,Idea.priority==x["priority"] if x.get("priority") else True] if z is not True))))
        return [{"id":x.id,"title":x.title,"stage":x.stage,"priority":x.priority} for x in session.scalars(q).all()]
    q=select(Note).where(Note.user_id==user.id)
    def note_pred(x):
        terms=[]
        if x.get("note_type"):terms.append(Note.type==x["note_type"])
        if x.get("status"):terms.append(Note.status==x["status"])
        if x.get("has_unresolved_questions"):terms.append(select(ResearchQuestion.id).where(ResearchQuestion.originating_note_id==Note.id,ResearchQuestion.status.in_(("open","partially_answered"))).exists())
        return and_(*terms) if terms else True
    q=q.where(groups(f,note_pred))
    return [serialized_note(session,x) for x in session.scalars(q.order_by(Note.updated_at.desc())).all()]

@app.get("/api/saved-views/defaults")
def default_views():
    return [{"name":"Critical unresolved questions","resource":"questions","filters":{"status":"open","priority":"critical"}},{"name":"Ideas worth investigating","resource":"ideas","filters":{"stage":"worth_investigating"}},{"name":"Open forecasts","resource":"forecasts","filters":{"status":"open"}},{"name":"Notes with unresolved questions","resource":"notes","filters":{"has_unresolved_questions":True}}]

@app.get("/api/research-reviews/{period}")
def research_review(period:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    if period not in {"daily","weekly"}:raise HTTPException(422,"Period must be daily or weekly")
    now=datetime.now(timezone.utc); days=1 if period=="daily" else 7
    since=now.replace(hour=0,minute=0,second=0,microsecond=0)
    from datetime import timedelta
    since-=timedelta(days=days-1)
    notes=session.scalars(select(Note).where(Note.user_id==user.id,Note.created_at>=since).order_by(Note.created_at.desc())).all()
    updates=session.scalars(select(ThinkingUpdate).where(ThinkingUpdate.user_id==user.id,ThinkingUpdate.created_at>=since).order_by(ThinkingUpdate.created_at.desc())).all()
    questions=session.scalars(select(ResearchQuestion).where(ResearchQuestion.user_id==user.id,ResearchQuestion.status.in_(("open","partially_answered"))).order_by(ResearchQuestion.priority.desc()).limit(10)).all()
    forecasts=session.scalars(select(Forecast).where(Forecast.user_id==user.id,Forecast.status=="resolved",Forecast.resolved_at>=since)).all()
    return {"period":period,"from":since.isoformat(),"to":now.isoformat(),"new_notes":len(notes),"thinking_updates":[{"id":x.id,"direction":x.change_direction,"reason":x.change_reason,"at":x.created_at.isoformat()} for x in updates],"open_questions":[{"id":x.id,"question":x.question,"priority":x.priority} for x in questions],"resolved_forecasts":[{"id":x.id,"metric":x.metric_name,"outcome":x.outcome} for x in forecasts]}

@app.post("/api/metric-cards")
def create_metric_card(payload:MetricCardRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    security=_security_for_ticker(session,payload.ticker)
    if payload.note_id:_owned_note(session,payload.note_id,user.id)
    if payload.source_id and not session.scalar(select(Source).where(Source.id==payload.source_id,Source.user_id==user.id)):raise HTTPException(404,"Source not found")
    if payload.forecast_id and not session.scalar(select(Forecast).where(Forecast.id==payload.forecast_id,Forecast.user_id==user.id)):raise HTTPException(404,"Forecast not found")
    value=MetricCard(user_id=user.id,security_id=security.id if security else None,note_id=payload.note_id,source_id=payload.source_id,forecast_id=payload.forecast_id,metric_name=payload.metric_name,value=payload.value,period=payload.period,value_unit=payload.value_unit,prior_value=payload.prior_value,consensus_value=payload.consensus_value,interpretation=payload.interpretation,data_json=payload.data);session.add(value);session.commit();return {"id":value.id,"metric_name":value.metric_name,"value":float(value.value),"period":value.period}

@app.get("/api/metric-cards")
def metric_cards(ticker:str|None=None,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(MetricCard).where(MetricCard.user_id==user.id)
    if ticker:
        security=_security_for_ticker(session,ticker);q=q.where(MetricCard.security_id==security.id) if security else q.where(False)
    return [{"id":x.id,"metric_name":x.metric_name,"value":float(x.value),"unit":x.value_unit,"period":x.period,"data":x.data_json} for x in session.scalars(q.order_by(MetricCard.created_at.desc())).all()]

@app.post("/api/tables/parse")
def parse_table(payload:TableParseRequest):
    lines=[x.strip() for x in payload.text.strip().splitlines() if x.strip()]
    rows=[]
    for line in lines:
        cells=[x.strip() for x in (line.strip("|").split("|") if "|" in line else line.split("\t"))]
        if cells and not all(set(x)<=set("-: ") for x in cells):rows.append(cells)
    if len(rows)<2:raise HTTPException(422,"Provide a header and at least one data row")
    width=len(rows[0])
    if width>30 or any(len(x)!=width for x in rows):raise HTTPException(422,"Table rows must have a consistent, safe column count")
    return {"columns":rows[0],"rows":rows[1:]}

@app.post("/api/charts")
def chart_config(payload:ChartRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    if payload.chart_type not in {"line","bar","scatter"}:raise HTTPException(422,"Unsupported chart type")
    card=session.scalar(select(MetricCard).where(MetricCard.id==payload.metric_card_id,MetricCard.user_id==user.id))
    if not card:raise HTTPException(404,"Metric card not found")
    data=card.data_json or {};points=data.get("points",[])
    if not isinstance(points,list) or not all(isinstance(x,dict) and "x" in x and "y" in x for x in points):raise HTTPException(422,"Metric card needs structured points with x and y values")
    return {"type":payload.chart_type,"title":card.metric_name,"series":[{"name":card.metric_name,"points":points}],"unit":card.value_unit}

@app.post("/api/ideas")
def create_idea(payload:IdeaRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    stages={"spark","worth_investigating","active_research","candidate_thesis","waiting_for_trigger","dormant","rejected","promoted_to_thesis"}
    if payload.stage not in stages or payload.priority not in {"low","medium","high","critical"}:raise HTTPException(422,"Invalid idea stage or priority")
    if payload.originating_note_id:_owned_note(session,payload.originating_note_id,user.id)
    if payload.source_id and not session.scalar(select(Source).where(Source.id==payload.source_id,Source.user_id==user.id)):raise HTTPException(404,"Source not found")
    value=Idea(user_id=user.id,title=payload.title,description=payload.description,stage=payload.stage,priority=payload.priority,originating_note_id=payload.originating_note_id,source_id=payload.source_id,why_it_matters=payload.why_it_matters,why_now=payload.why_now,next_step=payload.next_step,rejection_reason=payload.rejection_reason);session.add(value);session.flush()
    for symbol in set(payload.ticker_symbols):
        security=_security_for_ticker(session,symbol)
        if not security:security=Security(symbol=symbol.upper());session.add(security);session.flush()
        session.add(IdeaSecurity(idea_id=value.id,security_id=security.id))
    session.commit();return {"id":value.id,"title":value.title,"stage":value.stage}

@app.get("/api/ideas")
def ideas(stage:str|None=None,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(Idea).where(Idea.user_id==user.id)
    if stage:q=q.where(Idea.stage==stage)
    rows=session.scalars(q.order_by(Idea.updated_at.desc())).all();return [{"id":x.id,"title":x.title,"description":x.description,"stage":x.stage,"priority":x.priority,"next_step":x.next_step,"updated_at":x.updated_at.isoformat()} for x in rows]

@app.post("/api/ideas/{idea_id}/promote")
def promote_idea(idea_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    idea=session.scalar(select(Idea).where(Idea.id==idea_id,Idea.user_id==user.id))
    if not idea:raise HTTPException(404,"Idea not found")
    symbols=session.scalars(select(Security.symbol).join(IdeaSecurity,IdeaSecurity.security_id==Security.id).where(IdeaSecurity.idea_id==idea.id)).all();body=(" ".join("$"+x for x in symbols)+" "+(idea.description or idea.title)).strip();note=create_note(session,user_id=user.id,parsed=parse_note(body,"thesis"),title=idea.title,status="published",quotes={});idea.stage="promoted_to_thesis";idea.promoted_thesis_note_id=note.id
    if idea.originating_note_id:session.add(NoteRelationship(user_id=user.id,from_note_id=note.id,to_note_id=idea.originating_note_id,relationship_type="converts_to",created_by_workflow="idea_promotion"))
    session.commit();return serialized_note(session,note)

@app.get("/api/workspaces/daily")
def daily_workspace(user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    now=datetime.now(timezone.utc)
    inbox=session.scalars(select(InboxItem).where(InboxItem.user_id==user.id,InboxItem.status=="unprocessed").order_by(InboxItem.received_at.desc()).limit(20)).all()
    questions=session.scalars(select(ResearchQuestion).where(ResearchQuestion.user_id==user.id,ResearchQuestion.status.in_(("open","partially_answered")),or_(ResearchQuestion.priority=="critical",ResearchQuestion.due_at<=now)).order_by(ResearchQuestion.priority.desc()).limit(20)).all()
    drafts=session.scalars(select(Note).where(Note.user_id==user.id,Note.status=="draft").order_by(Note.updated_at.desc()).limit(10)).all()
    return {"inbox":[{"id":x.id,"title":x.title,"type":x.item_type} for x in inbox],"questions":[{"id":x.id,"question":x.question,"priority":x.priority} for x in questions],"drafts":[{"id":x.id,"title":x.title or x.body[:80]} for x in drafts],"reviews":research_review("daily",user,session)["thinking_updates"]}

@app.post("/api/workspaces/weekly")
def weekly_workspace(payload:WeeklyReviewRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    from datetime import timedelta
    now=datetime.now(timezone.utc);start=(payload.week_start or now).replace(hour=0,minute=0,second=0,microsecond=0);start-=timedelta(days=start.weekday());end=start+timedelta(days=7)
    summary={"notes":session.scalar(select(func.count(Note.id)).where(Note.user_id==user.id,Note.created_at>=start,Note.created_at<end)) or 0,"ideas":session.scalar(select(func.count(Idea.id)).where(Idea.user_id==user.id,Idea.created_at>=start,Idea.created_at<end)) or 0,"evidence":session.scalar(select(func.count(Evidence.id)).where(Evidence.user_id==user.id,Evidence.created_at>=start,Evidence.created_at<end)) or 0,"questions_created":session.scalar(select(func.count(ResearchQuestion.id)).where(ResearchQuestion.user_id==user.id,ResearchQuestion.created_at>=start,ResearchQuestion.created_at<end)) or 0,"forecasts":session.scalar(select(func.count(Forecast.id)).where(Forecast.user_id==user.id,Forecast.created_at>=start,Forecast.created_at<end)) or 0,"sources":session.scalar(select(func.count(Source.id)).where(Source.user_id==user.id,Source.created_at>=start,Source.created_at<end)) or 0}
    review=session.scalar(select(WeeklyReview).where(WeeklyReview.user_id==user.id,WeeklyReview.week_start==start)) or WeeklyReview(user_id=user.id,week_start=start,week_end=end);review.summary_json=summary;review.conclusions_json=payload.conclusions;review.completed_at=now if payload.complete else None;session.add(review);session.commit();return {"id":review.id,"week_start":start.isoformat(),"summary":summary,"completed":bool(review.completed_at)}

@app.get("/api/patterns")
def patterns(minimum_sample:int=3,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    rows=[]
    ticker_rows=session.execute(select(Security.symbol,func.count(Note.id)).join(NoteSecurityMention,NoteSecurityMention.security_id==Security.id).join(Note,Note.id==NoteSecurityMention.note_id).where(Note.user_id==user.id).group_by(Security.symbol).having(func.count(Note.id)>=minimum_sample)).all()
    for symbol,count in ticker_rows:
        thesis_count=session.scalar(select(func.count(Note.id)).join(NoteSecurityMention,NoteSecurityMention.note_id==Note.id).join(Security,Security.id==NoteSecurityMention.security_id).where(Note.user_id==user.id,Security.symbol==symbol,Note.type=="thesis")) or 0
        if not thesis_count:rows.append({"title":f"${symbol} has research volume but no thesis","rule":"At least minimum_sample notes and zero thesis notes","count":count,"low_sample":count<5,"ticker":symbol})
    unresolved=session.scalar(select(func.count(ResearchQuestion.id)).where(ResearchQuestion.user_id==user.id,ResearchQuestion.status.in_(("open","partially_answered")))) or 0
    if unresolved>=minimum_sample:rows.append({"title":"Open research-question backlog","rule":"Count of unresolved questions","count":unresolved,"low_sample":unresolved<5})
    forecasts=session.scalars(select(Forecast).where(Forecast.user_id==user.id,Forecast.status=="resolved")).all()
    if len(forecasts)>=minimum_sample:
        correct=[x for x in forecasts if x.outcome=="correct"];rows.append({"title":"Forecast resolution accuracy","rule":"Resolved forecasts classified correct divided by all resolved forecasts","count":len(forecasts),"value":len(correct)/len(forecasts),"low_sample":len(forecasts)<5,"record_ids":[x.id for x in forecasts]})
        errors=[float(x.error_percentage) for x in forecasts if x.error_percentage is not None]
        if errors:rows.append({"title":"Forecast bias","rule":"Mean signed percentage error across resolved point forecasts","count":len(errors),"value":sum(errors)/len(errors),"low_sample":len(errors)<5,"record_ids":[x.id for x in forecasts if x.error_percentage is not None]})
    challenged=session.scalars(select(Assumption).where(Assumption.user_id==user.id,Assumption.status=="challenged")).all()
    if len(challenged)>=minimum_sample:rows.append({"title":"Challenged assumptions need resolution","rule":"Assumptions currently marked challenged","count":len(challenged),"low_sample":len(challenged)<5,"record_ids":[x.id for x in challenged]})
    calls=session.scalars(select(TrackedCall).where(TrackedCall.user_id==user.id,TrackedCall.status.in_(("closed","invalidated")))).all()
    if len(calls)>=minimum_sample:
        invalidated=[x for x in calls if x.status=="invalidated"];rows.append({"title":"Call invalidation rate","rule":"Invalidated terminal calls divided by terminal calls","count":len(calls),"value":len(invalidated)/len(calls),"low_sample":len(calls)<5,"record_ids":[x.id for x in calls]})
    return rows


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
    call_ids = session.execute(
        statement.with_only_columns(TrackedCall.id, order)
        .distinct()
        .order_by(order)
        .offset(max(0, offset))
        .limit(min(max(1, limit), 200))
    ).all()
    calls = [session.get(TrackedCall, call_id) for call_id, _ in call_ids]
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

def _sync_authorized(request: Request, session: Session) -> BrokerageConnection:
    token = request.headers.get("X-FieldNotes-Sync-Token", "")
    token_hash=sha256(token.encode()).hexdigest() if token else ''
    connection=session.scalar(select(BrokerageConnection).where(BrokerageConnection.sync_token_hash==token_hash, BrokerageConnection.provider=="ibkr"))
    # Legacy global token remains supported only when explicitly configured.
    if not connection and settings.ibkr_sync_token and token==settings.ibkr_sync_token:
        connection=None
    elif not connection:
        raise HTTPException(status_code=401, detail="Invalid sync credential")
    return connection

@app.get("/api/integrations/ibkr/status")
def ibkr_status(user: CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    return [{"id":c.id,"display_name":c.display_name,"status":c.status,"last_synced_at":c.last_synced_at,"configured":bool(c.sync_token_hash)} for c in session.scalars(select(BrokerageConnection).where(BrokerageConnection.user_id==user.id,BrokerageConnection.provider=="ibkr")).all()]

@app.post("/api/integrations/ibkr/connect")
def ibkr_connect(payload:IBKRConnectionRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    connection=BrokerageConnection(user_id=user.id,provider="ibkr",display_name=payload.display_name,status="awaiting_sync",metadata_json={"host":payload.host,"port":payload.port,"client_id":payload.client_id})
    token=secrets.token_urlsafe(32);connection.sync_token_hash=sha256(token.encode()).hexdigest();session.add(connection);session.commit()
    return {"connection":{"id":connection.id,"status":connection.status,"display_name":connection.display_name},"sync_token":token,"agent_config":{"FIELDNOTES_API_URL":"<your FieldNotes URL>","FIELDNOTES_SYNC_TOKEN":token,"IBKR_HOST":payload.host,"IBKR_PORT":str(payload.port),"IBKR_CLIENT_ID":str(payload.client_id)},"warning":"Save this token now; it is never shown again. FieldNotes is read-only and cannot trade."}

@app.post("/api/integrations/ibkr/{connection_id}/rotate-token")
def ibkr_rotate(connection_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    connection=session.scalar(select(BrokerageConnection).where(BrokerageConnection.id==connection_id,BrokerageConnection.user_id==user.id));
    if not connection:raise HTTPException(404,"Connection not found")
    token=secrets.token_urlsafe(32);connection.sync_token_hash=sha256(token.encode()).hexdigest();session.commit();return {"sync_token":token,"warning":"Replace the token in your local agent now; it is never shown again."}

@app.post("/api/integrations/ibkr/sync")
def ibkr_sync(payload: IBKRSyncRequest, request: Request, session: Session = Depends(get_session)):
    authorized_connection=_sync_authorized(request,session)
    account_hash = sha256(payload.account_id.encode()).hexdigest()
    connection = authorized_connection or session.scalar(select(BrokerageConnection).where(BrokerageConnection.user_id == payload.user_id, BrokerageConnection.provider == "ibkr"))
    if not connection:
        if not payload.user_id: raise HTTPException(401,"A provisioned connection is required")
        connection = BrokerageConnection(user_id=payload.user_id, provider="ibkr", display_name=payload.connection_name); session.add(connection); session.flush()
    account = session.scalar(select(BrokerageAccount).where(BrokerageAccount.connection_id == connection.id, BrokerageAccount.external_account_id_hash == account_hash))
    if not account:
        account = BrokerageAccount(connection_id=connection.id, external_account_id_hash=account_hash, display_name="IBKR account •" + payload.account_id[-4:], account_type=payload.account_type, base_currency=payload.base_currency); session.add(account); session.flush()
    existing = session.scalar(select(PortfolioPosition).where(PortfolioPosition.brokerage_account_id == account.id, PortfolioPosition.snapshot_at == payload.snapshot_at))
    if existing: return {"status": "ok", "idempotent_replay": True}
    for row in payload.positions:
        symbol = str(row["symbol"]).upper(); security = session.scalar(select(Security).where(Security.symbol == symbol)) or Security(symbol=symbol, currency=row.get("currency", payload.base_currency)); session.add(security); session.flush()
        session.add(PortfolioPosition(brokerage_account_id=account.id, security_id=security.id, external_contract_id=row.get("contract_id"), quantity=row["quantity"], average_cost=row.get("average_cost"), market_price=row.get("market_price"), market_value=row.get("market_value"), unrealized_pnl=row.get("unrealized_pnl"), realized_pnl=row.get("realized_pnl"), currency=row.get("currency", payload.base_currency), snapshot_at=payload.snapshot_at, metadata_json={"source": "ibkr_sync_agent"}))
    connection.last_synced_at = account.last_synced_at = payload.snapshot_at; connection.status="connected";session.commit(); log_event("ibkr_sync", user_id=connection.user_id, position_count=len(payload.positions))
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


@app.get("/api/company-workspaces")
def list_company_workspaces(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    preference = session.get(UserWorkspacePreference, user.id)
    active_security_id = preference.active_security_id if preference else None
    workspaces = session.execute(
        select(CompanyWorkspace, Security)
        .join(Security, Security.id == CompanyWorkspace.security_id)
        .where(CompanyWorkspace.user_id == user.id)
        .order_by(CompanyWorkspace.is_followed.desc(), Security.symbol)
    ).all()
    return [_workspace_payload(session, workspace, security, active_security_id) for workspace, security in workspaces]


@app.post("/api/company-workspaces")
def create_company_workspace(payload: CompanyWorkspaceRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    workspace, security = _company_workspace(session, user.id, payload.symbol, create=True)
    if payload.company_name is not None:
        security.company_name = payload.company_name.strip() or None
    workspace.company_description = payload.company_description
    workspace.business_model = payload.business_model
    workspace.is_followed = payload.is_followed
    preference = session.get(UserWorkspacePreference, user.id)
    if preference is None:
        preference = UserWorkspacePreference(user_id=user.id, active_security_id=security.id)
        session.add(preference)
    session.commit()
    return _workspace_payload(session, workspace, security, preference.active_security_id)


@app.get("/api/company-workspaces/active")
def active_company_workspace(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    preference = session.get(UserWorkspacePreference, user.id)
    if preference is None or preference.active_security_id is None:
        return None
    workspace = session.scalar(select(CompanyWorkspace).where(CompanyWorkspace.user_id == user.id, CompanyWorkspace.security_id == preference.active_security_id))
    security = session.get(Security, preference.active_security_id)
    return _workspace_payload(session, workspace, security, preference.active_security_id) if workspace and security else None


@app.delete("/api/company-workspaces/active")
def clear_active_company_workspace(user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    preference = session.get(UserWorkspacePreference, user.id)
    if preference:
        preference.active_security_id = None
        session.commit()
    return {"active": None}


@app.post("/api/company-workspaces/{symbol}/activate")
def activate_company_workspace(symbol: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    workspace, security = _company_workspace(session, user.id, symbol, create=True)
    preference = session.get(UserWorkspacePreference, user.id)
    if preference is None:
        preference = UserWorkspacePreference(user_id=user.id)
        session.add(preference)
    preference.active_security_id = security.id
    session.commit()
    return _workspace_payload(session, workspace, security, security.id)


@app.get("/api/company-workspaces/{symbol}")
def company_workspace_detail(symbol: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    workspace, security = _company_workspace(session, user.id, symbol)
    if workspace is None or security is None:
        raise HTTPException(status_code=404, detail="Company workspace not found")
    preference = session.get(UserWorkspacePreference, user.id)
    return _workspace_payload(session, workspace, security, preference.active_security_id if preference else None)


@app.put("/api/company-workspaces/{symbol}")
def update_company_workspace(symbol: str, payload: CompanyWorkspaceUpdateRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    workspace, security = _company_workspace(session, user.id, symbol)
    if workspace is None or security is None:
        raise HTTPException(status_code=404, detail="Company workspace not found")
    if payload.company_name is not None:
        security.company_name = payload.company_name.strip() or None
    if payload.company_description is not None:
        workspace.company_description = payload.company_description
    if payload.business_model is not None:
        workspace.business_model = payload.business_model
    if payload.is_followed is not None:
        workspace.is_followed = payload.is_followed
    session.commit()
    preference = session.get(UserWorkspacePreference, user.id)
    return _workspace_payload(session, workspace, security, preference.active_security_id if preference else None)


@app.get("/api/tickers/{symbol}")
async def ticker_detail(symbol: str, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    security = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not security:
        raise HTTPException(status_code=404, detail="Ticker not found")
    notes = session.scalars(select(Note).join(NoteSecurityMention, NoteSecurityMention.note_id == Note.id).where(Note.user_id == user.id, NoteSecurityMention.security_id == security.id).order_by(Note.created_at.desc())).all()
    calls = session.scalars(select(TrackedCall).join(TrackedCallLeg, TrackedCallLeg.tracked_call_id == TrackedCall.id).where(TrackedCall.user_id == user.id, TrackedCallLeg.security_id == security.id).order_by(TrackedCall.opened_at.desc())).all()
    quote = session.scalar(select(SecurityPrice).where(SecurityPrice.security_id == security.id).order_by(SecurityPrice.timestamp.desc()).limit(1))
    events = session.scalars(select(CallEvent).join(TrackedCall, TrackedCall.id == CallEvent.tracked_call_id).join(TrackedCallLeg, TrackedCallLeg.tracked_call_id == TrackedCall.id).where(TrackedCall.user_id == user.id, TrackedCallLeg.security_id == security.id).order_by(CallEvent.occurred_at.desc())).all()
    assumptions=session.scalars(select(Assumption).where(Assumption.user_id==user.id,Assumption.security_id==security.id).order_by(Assumption.updated_at.desc())).all()
    evidence=session.scalars(select(Evidence).where(Evidence.user_id==user.id,Evidence.security_id==security.id,Evidence.status=="active").order_by(Evidence.created_at.desc())).all()
    questions=session.scalars(select(ResearchQuestion).where(ResearchQuestion.user_id==user.id,ResearchQuestion.security_id==security.id,ResearchQuestion.status.in_(("open","partially_answered"))).order_by(ResearchQuestion.priority.desc())).all()
    forecasts=session.scalars(select(Forecast).where(Forecast.user_id==user.id,Forecast.security_id==security.id).order_by(Forecast.created_at.desc())).all()
    updates=session.scalars(select(ThinkingUpdate).where(ThinkingUpdate.user_id==user.id,ThinkingUpdate.security_id==security.id).order_by(ThinkingUpdate.created_at.desc())).all()
    return {"symbol": security.symbol, "company_name": security.company_name, "quote": {"price": float(quote.raw_price), "timestamp": quote.timestamp.isoformat(), "basis": quote.price_type} if quote else None, "notes": [serialized_note(session, note) for note in notes], "calls": [{"call": serialize_call(session, call), "returns": call_return_object(session, call)} for call in calls], "timeline": [{"type": event.event_type, "occurred_at": event.occurred_at.isoformat(), "explanation": event.explanation, "call_id": event.tracked_call_id} for event in events], "workspace":{"open_question_count":len(questions),"active_assumption_count":len([x for x in assumptions if x.status not in {"disproven","retired"}]),"last_substantive_update":updates[0].created_at.isoformat() if updates else None,"assumptions":[{"id":x.id,"statement":x.statement,"status":x.status,"importance":x.importance,"updated_at":x.updated_at.isoformat()} for x in assumptions],"evidence":[{"id":x.id,"statement":x.statement,"direction":x.evidence_direction,"strength":x.strength} for x in evidence],"questions":[{"id":x.id,"question":x.question,"priority":x.priority,"status":x.status} for x in questions],"forecasts":[{"id":x.id,"metric_name":x.metric_name,"status":x.status,"target_value":float(x.target_value) if x.target_value is not None else None,"value_unit":x.value_unit} for x in forecasts]}}


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
    parsed = _scope_parsed_to_active_company(session, user.id, parsed, payload.active_ticker)
    quotes = {}
    if parsed["tracked_calls"]:
        provider = YFinanceMarketDataProvider()
        quote_failures = {}
        symbols = {"SPY"}
        for call in parsed["tracked_calls"]:
            symbols.update([call.get("symbol"), call.get("long"), call.get("short")])
        symbols.discard(None)
        for symbol in symbols:
            try:
                quote = provider.get_latest_quote(symbol)
                quotes[symbol] = quote
            except Exception as exc:
                quote_failures[symbol] = str(exc)
        if quote_failures:
            raise HTTPException(status_code=503, detail={"message": "Tracked calls were not published because a reference quote could not be captured.", "failures": quote_failures})
    note = create_note(session, user_id=user.id, parsed=parsed, title=payload.title or capture_title(payload.body, parsed), status="published", quotes=quotes)
    link_note_source_url(session, user.id, note, payload.source_url)
    save_thesis_details(session, note.id, payload.thesis_details)
    _create_pending_questions(session, user.id, note, payload.pending_questions)
    session.commit()
    log_event("note_published", user_id=user.id, note_id=note.id, call_count=len(parsed["tracked_calls"]))
    return serialized_note(session, note)


@app.post("/api/capture")
def capture(payload: CaptureRequest, user: CurrentUser = Depends(get_current_user), session: Session = Depends(get_session)):
    item,parsed,replay=inbox_capture(session,user.id,payload.model_dump())
    session.commit(); return {"item":{"id":item.id,"status":item.status,"source_id":item.source_id,"title":item.title},"parse":parsed,"idempotent_replay":replay}

@app.get("/api/inbox")
def inbox(status:str|None=None,item_type:str|None=None,ticker:str|None=None,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    q=select(InboxItem).where(InboxItem.user_id==user.id)
    if status:q=q.where(InboxItem.status==status)
    if item_type:q=q.where(InboxItem.item_type==item_type)
    rows=session.scalars(q.order_by(InboxItem.received_at.desc())).all()
    return [{"id":x.id,"type":x.item_type,"status":x.status,"channel":x.channel,"title":x.title,"excerpt":(x.raw_text or '')[:300],"source_id":x.source_id,"received_at":x.received_at.isoformat(),"metadata":x.metadata_json} for x in rows]
@app.get("/api/inbox/{item_id}")
def inbox_detail(item_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    x=session.scalar(select(InboxItem).where(InboxItem.id==item_id,InboxItem.user_id==user.id));
    if not x:raise HTTPException(404,"Inbox item not found")
    return {"id":x.id,"title":x.title,"text":x.raw_text,"status":x.status,"source_id":x.source_id,"metadata":x.metadata_json}
@app.post("/api/inbox/{item_id}/create-note")
def inbox_to_draft(item_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    item=session.scalar(select(InboxItem).where(InboxItem.id==item_id,InboxItem.user_id==user.id));
    if not item:raise HTTPException(404,"Inbox item not found")
    parsed=parse_note(item.raw_text or item.title or "",'note'); note=create_note(session,user_id=user.id,parsed=parsed,title=item.title or "",status='draft')
    if item.source_id:session.add(NoteSource(note_id=note.id,source_id=item.source_id,relationship_type='derived_from',excerpt=(item.raw_text or '')[:500]))
    item.status='converted';item.processed_at=datetime.now(timezone.utc);session.commit();return serialized_note(session,note)
@app.post("/api/inbox/{item_id}/{action}")
def inbox_action(item_id:str,action:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    item=session.scalar(select(InboxItem).where(InboxItem.id==item_id,InboxItem.user_id==user.id));
    if not item or action not in {'archive','discard','retry'}:raise HTTPException(404,"Inbox item not found")
    item.status={'archive':'archived','discard':'discarded','retry':'unprocessed'}[action];session.commit();return {"id":item.id,"status":item.status}
@app.get("/api/sources")
def sources(user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)): return [{"id":s.id,"type":s.source_type,"title":s.title,"url":s.canonical_url,"excerpt":s.excerpt,"status":s.content_status} for s in session.scalars(select(Source).where(Source.user_id==user.id).order_by(Source.created_at.desc())).all()]
@app.get("/api/sources/{source_id}")
def source_detail(source_id:str,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    s=session.scalar(select(Source).where(Source.id==source_id,Source.user_id==user.id));
    if not s:raise HTTPException(404,"Source not found")
    return {"id":s.id,"title":s.title,"url":s.canonical_url,"content":s.cleaned_content,"excerpt":s.excerpt,"metadata":s.metadata_json}
@app.patch("/api/inbox/{item_id}")
def patch_inbox(item_id:str,payload:InboxPatchRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    item=session.scalar(select(InboxItem).where(InboxItem.id==item_id,InboxItem.user_id==user.id));
    if not item:raise HTTPException(404,"Inbox item not found")
    if payload.status:
        if payload.status not in {'unprocessed','reviewing','converted','published','archived','discarded','error'}:raise HTTPException(422,"Invalid inbox status")
        item.status=payload.status
    if payload.title is not None:item.title=payload.title[:500]
    if payload.text is not None:item.raw_text=payload.text
    item.metadata_json={**(item.metadata_json or {}),"user_tags":payload.tags or (item.metadata_json or {}).get('user_tags',[]),"user_tickers":payload.tickers or (item.metadata_json or {}).get('user_tickers',[])}
    session.commit();return {"id":item.id,"status":item.status}
@app.post("/api/inbox/bulk")
def bulk_inbox(payload:BulkInboxRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    if payload.action not in {'archive','discard','processed','tag','ticker'}:raise HTTPException(422,"Unsupported bulk action")
    rows=session.scalars(select(InboxItem).where(InboxItem.user_id==user.id,InboxItem.id.in_(payload.item_ids))).all()
    for item in rows:
        if payload.action in {'archive','discard','processed'}: item.status={'archive':'archived','discard':'discarded','processed':'converted'}[payload.action]
        else:item.metadata_json={**(item.metadata_json or {}),('user_tags' if payload.action=='tag' else 'user_tickers'):[payload.tag if payload.action=='tag' else payload.ticker]}
    session.commit();return {"updated":len(rows)}
@app.post("/api/sources")
def create_source(payload:SourceRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    item,_,_=inbox_capture(session,user.id,{"channel":"manual","item_type":"source","title":payload.title,"text":payload.content,"url":payload.url,"external_id":payload.external_id,"metadata":payload.metadata})
    if not item.source_id:
        source=Source(user_id=user.id,source_type=payload.source_type,title=payload.title,raw_content=payload.content,cleaned_content=clean_html(payload.content),excerpt=clean_html(payload.content)[:500],content_status='available',metadata_json=payload.metadata);session.add(source);session.flush();item.source_id=source.id
    session.commit();return source_detail(item.source_id,user,session)
@app.patch("/api/sources/{source_id}")
def patch_source(source_id:str,payload:SourceRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    s=session.scalar(select(Source).where(Source.id==source_id,Source.user_id==user.id));
    if not s:raise HTTPException(404,"Source not found")
    if payload.title:s.title=payload.title[:500]
    if payload.content:s.cleaned_content=clean_html(payload.content);s.excerpt=s.cleaned_content[:500]
    s.metadata_json={**(s.metadata_json or {}),**payload.metadata};session.commit();return source_detail(s.id,user,session)
@app.post("/api/sources/{source_id}/link-note")
def link_source_note(source_id:str,payload:SourceLinkRequest,user:CurrentUser=Depends(get_current_user),session:Session=Depends(get_session)):
    source=session.scalar(select(Source).where(Source.id==source_id,Source.user_id==user.id));note=session.scalar(select(Note).where(Note.id==payload.note_id,Note.user_id==user.id))
    if not source or not note:raise HTTPException(404,"Source or note not found")
    if payload.relationship_type not in {'derived_from','supports','contradicts','references','quotes'}:raise HTTPException(422,"Invalid relationship")
    session.merge(NoteSource(note_id=note.id,source_id=source.id,relationship_type=payload.relationship_type,excerpt=payload.excerpt));session.commit();return {"note_id":note.id,"source_id":source.id}


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
@app.get("/inbox")
@app.get("/sources/{source_id}")
@app.get("/login")
def journal_route():
    """Serve the client shell for bookmarkable Phase 2 journal routes."""
    return FileResponse(web_root / "index.html")


app.mount("/", StaticFiles(directory=web_root, html=True), name="web")
