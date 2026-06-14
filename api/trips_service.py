"""api/trips_service.py — Trip orchestration (주입 repo, DB/FastAPI 비의존).

repo는 duck-typed: create_trip/get_trip/list_trips_for_user/get_member_role/
get_members/add_member/create_invite/get_invite 를 제공한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api import trips_logic as L


class TripNotFound(Exception):
    pass


class TripForbidden(Exception):
    pass


class InviteInvalid(Exception):
    pass


class InviteExpired(Exception):
    pass


def create_trip(repo, owner_user_id: str, title: str, destination: dict,
                start_date, end_date) -> dict:
    """Trip 생성 + owner 멤버 등록 → 직렬화된 trip.

    repo는 create_trip + add_member 두 호출을 하나의 트랜잭션으로 처리해야 한다
    (실 DB repo 구현 책임 — 중간 실패 시 owner 없는 orphan trip 방지).
    """
    trip = repo.create_trip(owner_user_id, title or "", destination, start_date, end_date)
    repo.add_member(trip["id"], owner_user_id, "owner")
    return L.serialize_trip(trip, repo.get_members(trip["id"]))


def list_trips(repo, user_id: str) -> list[dict]:
    """유저가 멤버인 Trip 목록(직렬화)."""
    trips = repo.list_trips_for_user(user_id)
    return [L.serialize_trip(t, repo.get_members(t["id"])) for t in trips]


def get_trip_detail(repo, trip_id: str, user_id: str) -> dict:
    """Trip 상세. 미존재 → TripNotFound, 비멤버 → TripForbidden."""
    trip = repo.get_trip(trip_id)
    if trip is None:
        raise TripNotFound(trip_id)
    if not L.is_member_role(repo.get_member_role(trip_id, user_id)):
        raise TripForbidden(trip_id)
    return L.serialize_trip(trip, repo.get_members(trip_id))


def create_invite(repo, trip_id: str, user_id: str, base_url: str,
                  now: datetime | None = None) -> dict:
    """초대 링크 발급(멤버만). → {token, invite_url, expires_at}."""
    trip = repo.get_trip(trip_id)
    if trip is None:
        raise TripNotFound(trip_id)
    if not L.is_member_role(repo.get_member_role(trip_id, user_id)):
        raise TripForbidden(trip_id)
    now = now or datetime.now(timezone.utc)
    token = L.generate_invite_token()
    expires_at = L.invite_expiry(now)
    repo.create_invite(token, trip_id, user_id, expires_at)
    return {"token": token, "invite_url": L.build_invite_url(base_url, token),
            "expires_at": expires_at}


def join_trip(repo, token: str, user_id: str,
              now: datetime | None = None) -> dict:
    """초대 토큰으로 합류. 무효 → InviteInvalid, 만료 → InviteExpired. → trip 상세.

    이미 멤버인 유저의 재합류는 의도적으로 멱등(repo.add_member가 ON CONFLICT DO NOTHING).
    """
    invite = repo.get_invite(token)
    if invite is None:
        raise InviteInvalid(token)
    now = now or datetime.now(timezone.utc)
    if L.is_invite_expired(invite["expires_at"], now):
        raise InviteExpired(token)
    trip_id = invite["trip_id"]
    repo.add_member(trip_id, user_id, "member")
    trip = repo.get_trip(trip_id)
    return L.serialize_trip(trip, repo.get_members(trip_id))
