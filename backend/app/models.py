from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def uid() -> str:
    return str(uuid4())


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), default="local-user", index=True)
    type: Mapped[str] = mapped_column(String(32), default="note")
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="published")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    normalized_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[str] = mapped_column(String(12), default="user")


class Security(Base):
    __tablename__ = "securities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    active: Mapped[bool] = mapped_column(default=True)


class CompanyWorkspace(Base):
    """An analyst-owned research workspace layered over the global security master."""
    __tablename__ = "company_workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), index=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_followed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "security_id", name="uq_company_workspace_user_security"),)


class UserWorkspacePreference(Base):
    __tablename__ = "user_workspace_preferences"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    active_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class SecurityPrice(Base):
    __tablename__ = "security_prices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    raw_price: Mapped[float] = mapped_column(Numeric(16, 6))
    adjusted_price: Mapped[float | None] = mapped_column(Numeric(16, 6), nullable=True)
    price_type: Mapped[str] = mapped_column(String(32), default="latest_available")
    provider: Mapped[str] = mapped_column(String(64), default="yfinance")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (Index("ix_security_prices_security_timestamp", "security_id", "timestamp"),)


class CallEvent(Base):
    __tablename__ = "call_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    tracked_call_id: Mapped[str | None] = mapped_column(ForeignKey("tracked_calls.id"), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    __table_args__ = (UniqueConstraint("tracked_call_id", "idempotency_key", name="uq_call_event_idempotency"),)


# Phase 2 normalized journal domain. Existing metadata_json is retained only as
# a legacy import source; new financial records are represented by these rows.
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(64), default="local-development")
    auth_provider_user_id: Mapped[str] = mapped_column(String(255), default="local-user")
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    default_benchmark_security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class NoteRevision(Base):
    __tablename__ = "note_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32))
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("note_id", "revision_number", name="uq_note_revision_number"),)


class NoteTag(Base):
    __tablename__ = "note_tags"
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class NoteSecurityMention(Base):
    __tablename__ = "note_security_mentions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), index=True)
    raw_token: Mapped[str] = mapped_column(String(64))
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class TrackedCall(Base):
    __tablename__ = "tracked_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    originating_note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    call_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    benchmark_security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversed_from_call_id: Mapped[str | None] = mapped_column(ForeignKey("tracked_calls.id"), nullable=True)
    closing_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    invalidation_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    legacy_metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class TrackedCallLeg(Base):
    __tablename__ = "tracked_call_legs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tracked_call_id: Mapped[str] = mapped_column(ForeignKey("tracked_calls.id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10))
    leg_order: Mapped[int] = mapped_column(Integer)
    entry_price_raw: Mapped[float] = mapped_column(Numeric(18, 6))
    entry_price_adjusted: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    entry_quote_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price_type: Mapped[str] = mapped_column(String(32))
    entry_market_session: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entry_provider: Mapped[str] = mapped_column(String(64))
    entry_currency: Mapped[str] = mapped_column(String(8), default="USD")
    exit_price_raw: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_price_adjusted: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_quote_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exit_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("tracked_call_id", "leg_order", name="uq_call_leg_order"),)


class CallBenchmarkSnapshot(Base):
    __tablename__ = "call_benchmark_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tracked_call_id: Mapped[str] = mapped_column(ForeignKey("tracked_calls.id"), unique=True, index=True)
    benchmark_security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"))
    entry_price_raw: Mapped[float] = mapped_column(Numeric(18, 6))
    entry_price_adjusted: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    entry_quote_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price_type: Mapped[str] = mapped_column(String(32))
    entry_provider: Mapped[str] = mapped_column(String(64))
    exit_price_raw: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_price_adjusted: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    exit_quote_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exit_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class NoteRelationship(Base):
    __tablename__ = "note_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    from_note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    to_note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(32), default="update_of")
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_workflow: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("from_note_id", "to_note_id", "relationship_type", name="uq_note_relationship"), CheckConstraint("from_note_id <> to_note_id", name="ck_note_relationship_not_self"))


# The reasoning ledger is deliberately normalized: these records are queried by
# ticker, thesis and status and must not be hidden in note metadata.
class ThinkingUpdate(Base):
    __tablename__ = "thinking_updates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True, index=True)
    update_note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), index=True)
    prior_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    tracked_call_id: Mapped[str | None] = mapped_column(ForeignKey("tracked_calls.id"), nullable=True)
    change_direction: Mapped[str] = mapped_column(String(16), default="unchanged")
    confidence_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_after: Mapped[str | None] = mapped_column(String(16), nullable=True)
    thesis_state_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thesis_state_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_before: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_after: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    horizon_before_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horizon_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Assumption(Base):
    __tablename__ = "assumptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True, index=True)
    thesis_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    originating_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    statement: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="untested", index=True)
    importance: Mapped[str] = mapped_column(String(16), default="medium")
    current_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    value_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expected_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_period: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class AssumptionEvent(Base):
    __tablename__ = "assumption_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    assumption_id: Mapped[str] = mapped_column(ForeignKey("assumptions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    from_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True, index=True)
    originating_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    source_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    statement: Mapped[str] = mapped_column(Text)
    evidence_direction: Mapped[str] = mapped_column(String(16), default="contextual")
    strength: Mapped[str] = mapped_column(String(16), default="moderate")
    status: Mapped[str] = mapped_column(String(16), default="active")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reliability: Mapped[str | None] = mapped_column(String(32), nullable=True)
    commentary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class EvidenceAssumption(Base):
    __tablename__ = "evidence_assumptions"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    assumption_id: Mapped[str] = mapped_column(ForeignKey("assumptions.id"), primary_key=True)

class EvidenceThesis(Base):
    __tablename__ = "evidence_theses"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    thesis_note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), primary_key=True)

class EvidenceForecast(Base):
    __tablename__ = "evidence_forecasts"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    forecast_id: Mapped[str] = mapped_column(ForeignKey("forecasts.id"), primary_key=True)

class EvidenceQuestion(Base):
    __tablename__ = "evidence_questions"
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("research_questions.id"), primary_key=True)


class ResearchQuestion(Base):
    __tablename__ = "research_questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True, index=True)
    originating_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    thesis_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    assumption_id: Mapped[str | None] = mapped_column(ForeignKey("assumptions.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    answer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    answered_by_source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class QuestionEvent(Base):
    __tablename__ = "question_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    question_id: Mapped[str] = mapped_column(ForeignKey("research_questions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    from_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    security_id: Mapped[str | None] = mapped_column(ForeignKey("securities.id"), nullable=True, index=True)
    originating_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    thesis_note_id: Mapped[str | None] = mapped_column(ForeignKey("notes.id"), nullable=True)
    assumption_id: Mapped[str | None] = mapped_column(ForeignKey("assumptions.id"), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(255))
    metric_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    forecast_type: Mapped[str] = mapped_column(String(16), default="point")
    target_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    lower_bound: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    upper_bound: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    probability: Mapped[float | None] = mapped_column(Numeric(6, 5), nullable=True)
    target_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    target_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    resolution_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    resolution_source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    error_percentage: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

class ForecastEvent(Base):
    __tablename__ = "forecast_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    forecast_id: Mapped[str] = mapped_column(ForeignKey("forecasts.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class SavedView(Base):
    __tablename__ = "saved_views"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120))
    resource: Mapped[str] = mapped_column(String(32))
    filters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_json: Mapped[dict] = mapped_column(JSON, default=dict)
    columns_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "resource", "name", name="uq_saved_view_name"),)

class MetricCard(Base):
    __tablename__="metric_cards"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True); security_id: Mapped[str|None]=mapped_column(ForeignKey("securities.id"),nullable=True,index=True); note_id: Mapped[str|None]=mapped_column(ForeignKey("notes.id"),nullable=True); source_id: Mapped[str|None]=mapped_column(ForeignKey("sources.id"),nullable=True); forecast_id: Mapped[str|None]=mapped_column(ForeignKey("forecasts.id"),nullable=True)
    metric_name: Mapped[str]=mapped_column(String(255)); metric_definition: Mapped[str|None]=mapped_column(Text,nullable=True); value: Mapped[float]=mapped_column(Numeric(20,6)); value_unit: Mapped[str|None]=mapped_column(String(32),nullable=True); period: Mapped[str]=mapped_column(String(128)); prior_value: Mapped[float|None]=mapped_column(Numeric(20,6),nullable=True); consensus_value: Mapped[float|None]=mapped_column(Numeric(20,6),nullable=True); source_excerpt: Mapped[str|None]=mapped_column(Text,nullable=True); interpretation: Mapped[str|None]=mapped_column(Text,nullable=True); data_json: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)

class Idea(Base):
    __tablename__="ideas"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True); originating_note_id: Mapped[str|None]=mapped_column(ForeignKey("notes.id"),nullable=True); source_id: Mapped[str|None]=mapped_column(ForeignKey("sources.id"),nullable=True); promoted_thesis_note_id: Mapped[str|None]=mapped_column(ForeignKey("notes.id"),nullable=True)
    title: Mapped[str]=mapped_column(String(500)); description: Mapped[str|None]=mapped_column(Text,nullable=True); why_it_matters: Mapped[str|None]=mapped_column(Text,nullable=True); why_now: Mapped[str|None]=mapped_column(Text,nullable=True); expressions: Mapped[str|None]=mapped_column(Text,nullable=True); next_step: Mapped[str|None]=mapped_column(Text,nullable=True); priority: Mapped[str]=mapped_column(String(16),default="medium"); stage: Mapped[str]=mapped_column(String(32),default="spark",index=True); review_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); rejection_reason: Mapped[str|None]=mapped_column(Text,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)

class IdeaSecurity(Base):
    __tablename__="idea_securities"; idea_id: Mapped[str]=mapped_column(ForeignKey("ideas.id"),primary_key=True); security_id: Mapped[str]=mapped_column(ForeignKey("securities.id"),primary_key=True)

class WeeklyReview(Base):
    __tablename__="weekly_reviews"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True); week_start: Mapped[datetime]=mapped_column(DateTime(timezone=True)); week_end: Mapped[datetime]=mapped_column(DateTime(timezone=True)); summary_json: Mapped[dict]=mapped_column(JSON,default=dict); conclusions_json: Mapped[dict]=mapped_column(JSON,default=dict); completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
    __table_args__=(UniqueConstraint("user_id","week_start",name="uq_weekly_review_period"),)


class ThesisDetails(Base):
    __tablename__ = "thesis_details"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(ForeignKey("notes.id"), unique=True, index=True)
    core_thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    catalysts_json: Mapped[list] = mapped_column(JSON, default=list)
    risks_json: Mapped[list] = mapped_column(JSON, default=list)
    invalidation_conditions_json: Mapped[list] = mapped_column(JSON, default=list)
    valuation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_time_horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class CallExpectation(Base):
    __tablename__ = "call_expectations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tracked_call_id: Mapped[str] = mapped_column(ForeignKey("tracked_calls.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_value: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    target_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    expected_return: Mapped[float | None] = mapped_column(Numeric(18, 6), nullable=True)
    time_horizon_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    catalyst_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class BrokerageConnection(Base):
    __tablename__ = "brokerage_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="ibkr")
    display_name: Mapped[str] = mapped_column(String(255), default="Interactive Brokers")
    status: Mapped[str] = mapped_column(String(32), default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sync_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class BrokerageAccount(Base):
    __tablename__ = "brokerage_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connection_id: Mapped[str] = mapped_column(ForeignKey("brokerage_connections.id"), index=True)
    external_account_id_hash: Mapped[str] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(8), default="USD")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("connection_id", "external_account_id_hash", name="uq_brokerage_account_external"),)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    brokerage_account_id: Mapped[str] = mapped_column(ForeignKey("brokerage_accounts.id"), index=True)
    security_id: Mapped[str] = mapped_column(ForeignKey("securities.id"), index=True)
    external_contract_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(20, 6))
    average_cost: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    market_price: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    market_value: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class UserReviewSettings(Base):
    __tablename__ = "user_review_settings"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    stale_warning_days: Mapped[int] = mapped_column(Integer, default=45)
    stale_critical_days: Mapped[int] = mapped_column(Integer, default=90)
    absolute_move_threshold: Mapped[float] = mapped_column(Numeric(8, 6), default=0.10)
    relative_move_threshold: Mapped[float] = mapped_column(Numeric(8, 6), default=0.08)
    daily_move_threshold: Mapped[float] = mapped_column(Numeric(8, 6), default=0.08)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ThesisReview(Base):
    __tablename__ = "thesis_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    tracked_call_id: Mapped[str] = mapped_column(ForeignKey("tracked_calls.id"), index=True)
    review_type: Mapped[str] = mapped_column(String(32), index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_before: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_after: Mapped[str | None] = mapped_column(String(16), nullable=True)
    thesis_state_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    thesis_state_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (Index("ix_review_pending_reason", "user_id", "tracked_call_id", "review_type", "review_status"),)

class Source(Base):
    __tablename__="sources"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True)
    source_type: Mapped[str]=mapped_column(String(32)); external_id: Mapped[str|None]=mapped_column(String(255),nullable=True); canonical_url: Mapped[str|None]=mapped_column(String(2000),nullable=True); original_url: Mapped[str|None]=mapped_column(String(2000),nullable=True)
    title: Mapped[str|None]=mapped_column(String(500),nullable=True); author: Mapped[str|None]=mapped_column(String(255),nullable=True); publisher: Mapped[str|None]=mapped_column(String(255),nullable=True); sender_name: Mapped[str|None]=mapped_column(String(255),nullable=True); sender_email: Mapped[str|None]=mapped_column(String(320),nullable=True); subject: Mapped[str|None]=mapped_column(String(500),nullable=True)
    published_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); received_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); captured_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); language: Mapped[str|None]=mapped_column(String(20),nullable=True); content_status: Mapped[str]=mapped_column(String(20),default="pending"); raw_content: Mapped[str|None]=mapped_column(Text,nullable=True); cleaned_content: Mapped[str|None]=mapped_column(Text,nullable=True); excerpt: Mapped[str|None]=mapped_column(Text,nullable=True); metadata_json: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
    __table_args__=(UniqueConstraint("user_id","source_type","external_id",name="uq_source_external"),)
class InboxItem(Base):
    __tablename__="inbox_items"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True); item_type: Mapped[str]=mapped_column(String(32)); status: Mapped[str]=mapped_column(String(20),default="unprocessed",index=True); channel: Mapped[str]=mapped_column(String(32)); title: Mapped[str|None]=mapped_column(String(500),nullable=True); raw_text: Mapped[str|None]=mapped_column(Text,nullable=True); source_id: Mapped[str|None]=mapped_column(ForeignKey("sources.id"),nullable=True,index=True); external_id: Mapped[str|None]=mapped_column(String(255),nullable=True); received_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); processed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); idempotency_key: Mapped[str|None]=mapped_column(String(128),nullable=True); metadata_json: Mapped[dict]=mapped_column(JSON,default=dict); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
    __table_args__=(UniqueConstraint("user_id","channel","external_id",name="uq_inbox_external"),UniqueConstraint("user_id","idempotency_key",name="uq_inbox_idempotency"))
class NoteSource(Base):
    __tablename__="note_sources"; note_id: Mapped[str]=mapped_column(ForeignKey("notes.id"),primary_key=True); source_id: Mapped[str]=mapped_column(ForeignKey("sources.id"),primary_key=True); relationship_type: Mapped[str]=mapped_column(String(32),default="derived_from"); excerpt: Mapped[str|None]=mapped_column(Text,nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
class SourceSecurityMention(Base):
    __tablename__="source_security_mentions"; source_id: Mapped[str]=mapped_column(ForeignKey("sources.id"),primary_key=True); security_id: Mapped[str]=mapped_column(ForeignKey("securities.id"),primary_key=True); raw_token: Mapped[str]=mapped_column(String(64)); detection_method: Mapped[str]=mapped_column(String(32),default="explicit"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
class SourceTag(Base):
    __tablename__="source_tags"; source_id: Mapped[str]=mapped_column(ForeignKey("sources.id"),primary_key=True); tag_id: Mapped[str]=mapped_column(ForeignKey("tags.id"),primary_key=True); detection_method: Mapped[str]=mapped_column(String(32),default="explicit"); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow)
class EmailConnection(Base):
    __tablename__="email_connections"; id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid); user_id: Mapped[str]=mapped_column(String(36),index=True); provider: Mapped[str]=mapped_column(String(32)); email_address: Mapped[str]=mapped_column(String(320)); status: Mapped[str]=mapped_column(String(32),default="disconnected"); encrypted_access_data: Mapped[str|None]=mapped_column(Text,nullable=True); cursor: Mapped[str|None]=mapped_column(String(500),nullable=True); last_synced_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=datetime.utcnow,onupdate=datetime.utcnow)
