"""api/trips_logic.py — Trip/초대 순수 헬퍼 (DB/FastAPI 비의존)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

_MEMBER_ROLES = {"owner", "member"}


def generate_trip_id() -> str:
    """URL-safe 한 Trip ID."""
    return secrets.token_urlsafe(12)


def generate_invite_token() -> str:
    """URL-safe 한 초대 토큰."""
    return secrets.token_urlsafe(24)


def invite_expiry(now: datetime, days: int = 14) -> datetime:
    """현재 시각 기준 초대 만료 시각."""
    return now + timedelta(days=days)


def is_invite_expired(expires_at: datetime, now: datetime) -> bool:
    """만료 여부. 경계(expires_at == now)는 만료로 처리(보수적 — 초대 링크 안전)."""
    return expires_at <= now


def build_invite_url(base_url: str, token: str) -> str:
    """프론트 합류 링크 생성."""
    return f"{base_url.rstrip('/')}/trips/join?token={token}"


def is_member_role(role: str | None) -> bool:
    """유효한 멤버 역할인지(=Trip 접근 권한 보유)."""
    return role in _MEMBER_ROLES


def serialize_trip(trip: dict, members: list[dict]) -> dict:
    """Trip row + 멤버 목록 → API 응답 dict. 호출자가 id·owner_user_id 존재를 보장한다(DB row)."""
    return {
        "id": trip.get("id"),
        "owner_user_id": trip.get("owner_user_id"),
        "title": trip.get("title", ""),
        "destination": trip.get("destination"),
        "start_date": trip.get("start_date"),
        "end_date": trip.get("end_date"),
        "created_at": trip.get("created_at"),
        "members": members,
    }
