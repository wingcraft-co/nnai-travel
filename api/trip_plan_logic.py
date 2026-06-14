"""api/trip_plan_logic.py — 공동 플래너(plan item) 순수 헬퍼 (DB/FastAPI 비의존)."""
from __future__ import annotations

ALLOWED_CATEGORIES = ("관광", "식사", "이동", "숙소", "액티비티", "기타")


def is_valid_category(category) -> bool:
    """category가 허용 목록에 있는지."""
    return category in ALLOWED_CATEGORIES


def serialize_plan_item(row: dict) -> dict:
    """plan item DB row → API 응답 dict."""
    return {
        "id": row.get("id"),
        "trip_id": row.get("trip_id"),
        "day": row.get("day"),
        "time": row.get("time"),
        "place": row.get("place"),
        "category": row.get("category"),
        "memo": row.get("memo"),
        "added_by": row.get("added_by"),
        "created_at": row.get("created_at"),
    }


def can_edit_item(item: dict, user_id: str, trip_role: str | None) -> bool:
    """수정/삭제 권한: 항목 작성자이거나 Trip owner."""
    if item.get("added_by") == user_id:
        return True
    return trip_role == "owner"
