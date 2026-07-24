"""Canonical, deterministic ticker thinking timeline and evolution sentences."""
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import CallEvent, Note, NoteRevision, NoteSecurityMention, PortfolioPosition, Security, ThesisReview, TrackedCall, TrackedCallLeg

def ticker_timeline(session: Session, user_id: str, symbol: str, kind="all", order="desc"):
    security = session.scalar(select(Security).where(Security.symbol == symbol.upper()))
    if not security: return []
    events=[]
    notes=session.scalars(select(Note).join(NoteSecurityMention).where(Note.user_id==user_id, NoteSecurityMention.security_id==security.id)).all()
    for note in notes:
        events.append({"type":"note_published", "category":"thinking", "at":note.published_at or note.created_at, "note_id":note.id, "excerpt":note.title or note.body[:160], "note_type":note.type})
        for revision in session.scalars(select(NoteRevision).where(NoteRevision.note_id==note.id, NoteRevision.revision_number>1)).all(): events.append({"type":"note_revised", "category":"thinking", "at":revision.edited_at, "note_id":note.id, "excerpt":revision.title or revision.body[:160]})
    calls=session.scalars(select(TrackedCall).join(TrackedCallLeg).where(TrackedCall.user_id==user_id, TrackedCallLeg.security_id==security.id)).all()
    for call in calls:
        for event in session.scalars(select(CallEvent).where(CallEvent.tracked_call_id==call.id)).all(): events.append({"type":"call_"+event.event_type, "category":"calls", "at":event.occurred_at, "call_id":call.id, "excerpt":event.explanation, "snapshot":event.snapshot_json})
        for review in session.scalars(select(ThesisReview).where(ThesisReview.tracked_call_id==call.id)).all(): events.append({"type":"review_"+review.review_status, "category":"reviews", "at":review.completed_at or review.created_at, "call_id":call.id, "review_id":review.id, "excerpt":review.explanation, "snapshot":review.snapshot_json, "review_type":review.review_type})
    positions=session.scalars(select(PortfolioPosition).where(PortfolioPosition.security_id==security.id).order_by(PortfolioPosition.snapshot_at)).all()
    if positions: events.append({"type":"portfolio_position_first_synced", "category":"portfolio", "at":positions[0].snapshot_at, "excerpt":"Portfolio position synced"})
    if kind != "all": events=[e for e in events if e["category"]==kind]
    return sorted(events, key=lambda e:e["at"], reverse=order!="asc")

def thinking_evolution(session, user_id, symbol, scope="all"):
    events=ticker_timeline(session,user_id,symbol, "all", "asc")
    if scope=="current_call":
        calls=[e.get("call_id") for e in events if e.get("call_id")]; events=[e for e in events if not calls or e.get("call_id")==calls[-1]]
    if len(events)<2: return {"scope":scope,"groups":[],"empty":True,"message":"Not enough recorded history to summarize the evolution of this view."}
    groups=defaultdict(list)
    for e in events:
        snapshot=e.get("snapshot") or {}; sentence=None
        if e["type"]=="call_opened": sentence="Initial thesis opened."
        elif e["type"]=="call_updated":
            before,after=snapshot.get("confidence_before"),snapshot.get("confidence_after")
            sentence=f"Confidence {'increased' if before and after and after>before else 'changed'} from {before} to {after}." if before and after and before!=after else "A price-aware thesis update was recorded."
        elif e["type"]=="call_expectation_updated":
            old,new=snapshot.get("old_target"),snapshot.get("new_target"); sentence=f"Target {'increased' if new and old and new>old else 'changed'} from ${old:g} to ${new:g}." if old is not None and new is not None else "Target was revised."
        elif e["type"]=="call_closed": sentence="The call was closed."
        elif e["type"]=="call_invalidated": sentence="The thesis was invalidated."
        elif e["type"]=="call_reversed": sentence="The view was reversed."
        elif e["type"]=="review_completed": sentence="A thesis review was completed."
        elif e["type"]=="note_published" and e.get("note_type") in {"observation","idea","thesis","question"}: sentence=f"A {e['note_type']} was added."
        if sentence: groups[e["at"].strftime("%b %Y")].append(sentence)
    return {"scope":scope,"groups":[{"month":month,"sentences":sentences} for month,sentences in groups.items()],"empty":not bool(groups)}
