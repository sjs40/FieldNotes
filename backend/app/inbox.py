"""Deterministic capture/source ingestion. No provider may publish a call."""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit,urlunsplit
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import InboxItem,Source,SourceSecurityMention,SourceTag,Security,Tag
from .parser import parse_note
def clean_html(value): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value or "")).strip()
def normalize_url(value):
 p=urlsplit(value); return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),p.query,''))
def attach_rules(session,source,text):
 parsed=parse_note(text or "x"); symbols=parsed["ticker_mentions"]; tags=parsed["tags"]
 for symbol in symbols:
  security=session.scalar(select(Security).where(Security.symbol==symbol))
  if security: session.merge(SourceSecurityMention(source_id=source.id,security_id=security.id,raw_token='$'+symbol,detection_method='explicit'))
 for name in tags:
  tag=session.scalar(select(Tag).where(Tag.normalized_name==name.lower()))
  if tag: session.merge(SourceTag(source_id=source.id,tag_id=tag.id,detection_method='explicit'))
 return parsed
def capture(session,user_id,payload):
 key=payload.get('idempotency_key'); existing=session.scalar(select(InboxItem).where(InboxItem.user_id==user_id,InboxItem.idempotency_key==key)) if key else None
 if existing:return existing,parse_note(existing.raw_text or existing.title or 'x'),True
 text=payload.get('text') or ''; url=payload.get('url'); item_type=payload.get('item_type','text'); received=payload.get('received_at') or datetime.now(timezone.utc)
 if isinstance(received,str): received=datetime.fromisoformat(received.replace('Z','+00:00'))
 source=None
 if url:
  canonical=normalize_url(url); source=session.scalar(select(Source).where(Source.user_id==user_id,Source.canonical_url==canonical))
  if not source: source=Source(user_id=user_id,source_type='article' if item_type=='url' else item_type,canonical_url=canonical,original_url=url,title=payload.get('title'),raw_content=text or None,cleaned_content=clean_html(text) or None,excerpt=clean_html(text)[:500] or None,content_status='available' if text else 'partial');session.add(source);session.flush();attach_rules(session,source,text)
 item=InboxItem(user_id=user_id,item_type=item_type,status='unprocessed',channel=payload.get('channel','web'),title=payload.get('title'),raw_text=text or None,source_id=source.id if source else None,external_id=payload.get('external_id'),received_at=received,idempotency_key=key,metadata_json=payload.get('metadata') or {})
 session.add(item);session.flush(); return item,parse_note(text or payload.get('title') or 'x'),False
