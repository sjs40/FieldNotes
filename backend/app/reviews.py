"""Deterministic thesis-review queue generation and serialization."""
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .journal import call_return_object, serialize_call
from .models import CallEvent, CallExpectation, ThesisReview, TrackedCall, UserReviewSettings

REVIEW_TYPES = {"scheduled", "stale", "large_move", "target_reached", "catalyst_due", "manual", "portfolio_position", "horizon"}
STATUSES = {"pending", "completed", "dismissed", "snoozed"}
OUTCOMES = {"maintain", "strengthen", "weaken", "close", "reverse", "invalidate", "needs_more_work", "worked_on_time", "worked_early", "delayed", "failed", "still_open"}

def now_utc(): return datetime.now(timezone.utc)
def aware(value): return value if value and value.tzinfo else value.replace(tzinfo=timezone.utc) if value else None

def settings_for(session: Session, user_id: str) -> UserReviewSettings:
    value = session.get(UserReviewSettings, user_id)
    if not value:
        value = UserReviewSettings(user_id=user_id); session.add(value); session.flush()
    return value

def last_activity(session: Session, call: TrackedCall):
    updated = session.scalar(select(CallEvent.occurred_at).where(CallEvent.tracked_call_id == call.id, CallEvent.event_type == "updated").order_by(CallEvent.occurred_at.desc()).limit(1))
    completed = session.scalar(select(ThesisReview.completed_at).where(ThesisReview.tracked_call_id == call.id, ThesisReview.review_status == "completed").order_by(ThesisReview.completed_at.desc()).limit(1))
    return max((aware(value) for value in (call.opened_at, updated, completed) if value), default=now_utc())

def _pending(session, call, review_type):
    return session.scalar(select(ThesisReview).where(ThesisReview.tracked_call_id == call.id, ThesisReview.review_type == review_type, ThesisReview.review_status.in_(("pending", "snoozed"))))

def add_pending(session, call, review_type, scheduled_for=None, metadata=None):
    existing = _pending(session, call, review_type)
    if existing: return existing, False
    review = ThesisReview(user_id=call.user_id, tracked_call_id=call.id, review_type=review_type, scheduled_for=scheduled_for, metadata_json=metadata or {})
    session.add(review); return review, True

def generate(session: Session, user_id: str, at=None):
    at = aware(at) or now_utc(); config = settings_for(session, user_id); created=[]
    for call in session.scalars(select(TrackedCall).where(TrackedCall.user_id == user_id, TrackedCall.status == "open")).all():
        age = (at - last_activity(session, call)).days
        severity = "critical" if age >= config.stale_critical_days else "warning" if age >= config.stale_warning_days else "fresh"
        if severity != "fresh":
            review, new = add_pending(session, call, "stale", metadata={"severity": severity, "days_since_activity": age})
            if new: created.append(review)
        expectation = session.scalar(select(CallExpectation).where(CallExpectation.tracked_call_id == call.id).order_by(CallExpectation.created_at.desc()))
        if expectation:
            if expectation.review_at and aware(expectation.review_at) <= at:
                review, new = add_pending(session, call, "scheduled", expectation.review_at); created += [review] if new else []
            if expectation.catalyst_at and aware(expectation.catalyst_at) <= at:
                review, new = add_pending(session, call, "catalyst_due", expectation.catalyst_at); created += [review] if new else []
            if expectation.time_horizon_days and (at - aware(call.opened_at)).days >= expectation.time_horizon_days:
                review, new = add_pending(session, call, "horizon", metadata={"horizon_days": expectation.time_horizon_days}); created += [review] if new else []
            payload = serialize_call(session, call)
            if payload.get("target_status") in {"reached", "passed"}:
                review, new = add_pending(session, call, "target_reached", metadata={"target_status": payload["target_status"]}); created += [review] if new else []
        returns = call_return_object(session, call); movement = abs(returns.get("pair_return", returns.get("directional_return", 0)))
        if movement >= float(config.absolute_move_threshold):
            prior = session.scalar(select(ThesisReview).where(ThesisReview.tracked_call_id == call.id, ThesisReview.review_type == "large_move"))
            if not prior:
                review, new = add_pending(session, call, "large_move", metadata={"threshold": float(config.absolute_move_threshold), "return": movement}); created += [review] if new else []
    return created

def serialize_review(session, review):
    call = session.get(TrackedCall, review.tracked_call_id)
    return {"id": review.id, "type": review.review_type, "status": review.review_status, "scheduled_for": review.scheduled_for.isoformat() if review.scheduled_for else None, "completed_at": review.completed_at.isoformat() if review.completed_at else None, "outcome": review.outcome, "explanation": review.explanation, "metadata": review.metadata_json, "snapshot": review.snapshot_json, "call": serialize_call(session, call) if call else None, "returns": call_return_object(session, call) if call else None}
