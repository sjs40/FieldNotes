from datetime import datetime
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


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
