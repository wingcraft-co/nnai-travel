"""api/trips.py — Trip 저장/초대 FastAPI 라우터 (얇은 어댑터).

로직은 api/trips_service.py. 이 모듈은 auth 게이팅·예외 매핑·repo 어댑터만 담당.
_DbRepo는 utils.db를 메서드 내부에서 lazy import 한다 — 모듈 로드 시 psycopg2를
끌어오지 않아야 CI에서 라우터 테스트(가짜 repo)가 실 DB 없이 동작하기 때문.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api import trips_service as SVC
from api import trips_logic as L
from api import trip_plan_service as PSVC

router = APIRouter()


class _DbRepo:
    """utils.db SQL 함수를 서비스가 기대하는 repo 인터페이스로 어댑트."""
    def create_trip(self, owner_user_id, title, destination, start_date, end_date):
        from utils.db import db_create_trip
        return db_create_trip(L.generate_trip_id(), owner_user_id, title,
                              destination, start_date, end_date)

    def get_trip(self, trip_id):
        from utils.db import db_get_trip
        return db_get_trip(trip_id)

    def list_trips_for_user(self, user_id):
        from utils.db import db_list_trips_for_user
        return db_list_trips_for_user(user_id)

    def get_member_role(self, trip_id, user_id):
        from utils.db import db_get_member_role
        return db_get_member_role(trip_id, user_id)

    def get_members(self, trip_id):
        from utils.db import db_get_members
        return db_get_members(trip_id)

    def add_member(self, trip_id, user_id, role):
        from utils.db import db_add_member
        return db_add_member(trip_id, user_id, role)

    def create_invite(self, token, trip_id, created_by, expires_at):
        from utils.db import db_create_invite
        return db_create_invite(token, trip_id, created_by, expires_at)

    def get_invite(self, token):
        from utils.db import db_get_invite
        return db_get_invite(token)

    def create_plan_item(self, trip_id, day, time, place, category, added_by, memo):
        from utils.db import db_create_plan_item
        return db_create_plan_item(trip_id, day, time, place, category, added_by, memo)

    def list_plan_items(self, trip_id):
        from utils.db import db_list_plan_items
        return db_list_plan_items(trip_id)

    def get_plan_item(self, item_id):
        from utils.db import db_get_plan_item
        return db_get_plan_item(item_id)

    def update_plan_item(self, item_id, day, time, place, category, memo):
        from utils.db import db_update_plan_item
        return db_update_plan_item(item_id, day, time, place, category, memo)

    def delete_plan_item(self, item_id):
        from utils.db import db_delete_plan_item
        return db_delete_plan_item(item_id)


def _repo():
    return _DbRepo()


def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")
    return user_id


def _frontend_base_url() -> str:
    return os.environ.get("FRONTEND_URL", "https://nnai.app")


class TripCreateRequest(BaseModel):
    title: str = Field(default="", max_length=100)
    destination: dict
    start_date: str | None = None
    end_date: str | None = None


class JoinRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


class PlanItemCreateRequest(BaseModel):
    day: int = Field(ge=1, le=60)
    time: str | None = Field(default=None, max_length=20)
    place: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=20)
    memo: str | None = Field(default=None, max_length=500)


class PlanItemUpdateRequest(BaseModel):
    day: int = Field(ge=1, le=60)
    time: str | None = Field(default=None, max_length=20)
    place: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=20)
    memo: str | None = Field(default=None, max_length=500)


@router.post("")
async def create_trip(req: TripCreateRequest, request: Request):
    user_id = _require_user(request)
    return SVC.create_trip(_repo(), user_id, req.title, req.destination,
                           req.start_date, req.end_date)


@router.get("")
async def list_trips(request: Request):
    user_id = _require_user(request)
    return {"trips": SVC.list_trips(_repo(), user_id)}


@router.get("/{trip_id}")
async def get_trip(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.get_trip_detail(_repo(), trip_id, user_id)
    except SVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except SVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.post("/{trip_id}/invites")
async def create_invite(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.create_invite(_repo(), trip_id, user_id, _frontend_base_url())
    except SVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except SVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.post("/join")
async def join_trip(req: JoinRequest, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.join_trip(_repo(), req.token, user_id)
    except SVC.InviteInvalid:
        raise HTTPException(status_code=400, detail="Invalid invite token.")
    except SVC.InviteExpired:
        raise HTTPException(status_code=410, detail="Invite link has expired.")


@router.post("/{trip_id}/plan-items")
async def add_plan_item(trip_id: str, req: PlanItemCreateRequest, request: Request):
    user_id = _require_user(request)
    try:
        return PSVC.add_plan_item(_repo(), trip_id, user_id, day=req.day, time=req.time,
                                  place=req.place, category=req.category, memo=req.memo)
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.InvalidPlanItem as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{trip_id}/plan-items")
async def list_plan_items(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return {"plan_items": PSVC.list_plan_items(_repo(), trip_id, user_id)}
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.patch("/{trip_id}/plan-items/{item_id}")
async def update_plan_item(trip_id: str, item_id: int, req: PlanItemUpdateRequest, request: Request):
    user_id = _require_user(request)
    try:
        return PSVC.update_plan_item(_repo(), trip_id, item_id, user_id, day=req.day,
                                     time=req.time, place=req.place, category=req.category,
                                     memo=req.memo)
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.PlanItemNotFound:
        raise HTTPException(status_code=404, detail="Plan item not found.")
    except PSVC.PlanItemForbidden:
        raise HTTPException(status_code=403, detail="No permission to edit this item.")
    except PSVC.InvalidPlanItem as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{trip_id}/plan-items/{item_id}")
async def delete_plan_item(trip_id: str, item_id: int, request: Request):
    user_id = _require_user(request)
    try:
        PSVC.delete_plan_item(_repo(), trip_id, item_id, user_id)
        return {"deleted": True}
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.PlanItemNotFound:
        raise HTTPException(status_code=404, detail="Plan item not found.")
    except PSVC.PlanItemForbidden:
        raise HTTPException(status_code=403, detail="No permission to delete this item.")
