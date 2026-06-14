"""api/trip_plan_service.py — 공동 플래너 orchestration (주입 repo, DB/FastAPI 비의존).

Trip 멤버십(Phase 5)을 재사용. repo는 get_trip/get_member_role(기존) +
create_plan_item/list_plan_items/get_plan_item/update_plan_item/delete_plan_item 제공.
"""
from __future__ import annotations

from api import trip_plan_logic as L
from api.trips_service import TripNotFound, TripForbidden
from api import trips_logic as TL


class PlanItemNotFound(Exception):
    pass


class PlanItemForbidden(Exception):
    pass


class InvalidPlanItem(Exception):
    pass


def _require_member(repo, trip_id: str, user_id: str) -> str:
    """Trip 존재 + 멤버 확인. 역할 문자열 반환. 미존재→TripNotFound, 비멤버→TripForbidden."""
    if repo.get_trip(trip_id) is None:
        raise TripNotFound(trip_id)
    role = repo.get_member_role(trip_id, user_id)
    if not TL.is_member_role(role):
        raise TripForbidden(trip_id)
    return role


def add_plan_item(repo, trip_id: str, user_id: str, day: int, time,
                  place: str, category: str, memo) -> dict:
    """계획 항목 추가(멤버). 잘못된 category/빈 place → InvalidPlanItem."""
    _require_member(repo, trip_id, user_id)
    if not L.is_valid_category(category):
        raise InvalidPlanItem(f"invalid category: {category}")
    if not place or not place.strip():
        raise InvalidPlanItem("place is required")
    row = repo.create_plan_item(trip_id, day, time, place.strip(), category, user_id, memo)
    return L.serialize_plan_item(row)


def list_plan_items(repo, trip_id: str, user_id: str) -> list[dict]:
    """계획 항목 목록(멤버)."""
    _require_member(repo, trip_id, user_id)
    return [L.serialize_plan_item(r) for r in repo.list_plan_items(trip_id)]


def _load_editable_item(repo, trip_id: str, item_id, user_id: str) -> dict:
    """수정/삭제 공통: 멤버 확인 + 항목 존재/소속/권한 확인 후 item 반환."""
    role = _require_member(repo, trip_id, user_id)
    item = repo.get_plan_item(item_id)
    if item is None or item.get("trip_id") != trip_id:
        raise PlanItemNotFound(item_id)
    if not L.can_edit_item(item, user_id, role):
        raise PlanItemForbidden(item_id)
    return item


def update_plan_item(repo, trip_id: str, item_id, user_id: str, *, day, time,
                     place, category, memo) -> dict:
    """계획 항목 수정(작성자 또는 owner). 부분 갱신은 호출자가 기존값과 병합해 전달."""
    _load_editable_item(repo, trip_id, item_id, user_id)
    if not L.is_valid_category(category):
        raise InvalidPlanItem(f"invalid category: {category}")
    if not place or not place.strip():
        raise InvalidPlanItem("place is required")
    row = repo.update_plan_item(item_id, day, time, place.strip(), category, memo)
    if row is None:
        raise PlanItemNotFound(item_id)
    return L.serialize_plan_item(row)


def delete_plan_item(repo, trip_id: str, item_id, user_id: str) -> None:
    """계획 항목 삭제(작성자 또는 owner)."""
    _load_editable_item(repo, trip_id, item_id, user_id)
    repo.delete_plan_item(item_id)
