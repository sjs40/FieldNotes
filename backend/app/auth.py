"""Supabase Auth integration for FastAPI resource ownership."""
from dataclasses import dataclass
import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from .config import settings
from .database import get_session
from .models import User


@dataclass
class CurrentUser:
    id: str
    email: str
    display_name: str | None


async def get_current_user(request: Request, session: Session = Depends(get_session)) -> CurrentUser:
    if not settings.authentication_enabled:
        # Local development only. Production refuses to start without Supabase
        # configuration so this path cannot be used publicly.
        if settings.is_production:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        user = session.get(User, "local-user")
        if not user:
            user = User(id="local-user", email="local@fieldnotes.invalid", display_name="Local user")
            session.add(user); session.commit()
        return CurrentUser(id=user.id, email=user.email, display_name=user.display_name)
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.get(f"{settings.supabase_url.rstrip('/')}/auth/v1/user", headers={"apikey": settings.supabase_publishable_key, "Authorization": authorization})
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    claims = response.json()
    user = session.get(User, claims["id"])
    if not user:
        user = User(id=claims["id"], email=claims.get("email") or f"{claims['id']}@supabase.invalid", display_name=(claims.get("user_metadata") or {}).get("full_name"), auth_provider="supabase", auth_provider_user_id=claims["id"])
        session.add(user); session.commit()
    return CurrentUser(id=user.id, email=user.email, display_name=user.display_name)
