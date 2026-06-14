"""tests/test_trip_plan_logic.py — 공동 플래너 순수 헬퍼 테스트"""
from api import trip_plan_logic as L


def test_allowed_categories():
    assert "관광" in L.ALLOWED_CATEGORIES
    assert "식사" in L.ALLOWED_CATEGORIES
    assert "이동" in L.ALLOWED_CATEGORIES
    assert "숙소" in L.ALLOWED_CATEGORIES

def test_is_valid_category():
    assert L.is_valid_category("관광") is True
    assert L.is_valid_category("기타") is True
    assert L.is_valid_category("아무거나") is False
    assert L.is_valid_category("") is False
    assert L.is_valid_category(None) is False

def test_serialize_plan_item():
    row = {"id": 5, "trip_id": "t1", "day": 1, "time": "09:00", "place": "우붓",
           "category": "관광", "memo": "아침 일찍", "added_by": "u1",
           "created_at": "2026-06-14T00:00:00Z"}
    out = L.serialize_plan_item(row)
    assert out["id"] == 5
    assert out["trip_id"] == "t1"
    assert out["day"] == 1
    assert out["place"] == "우붓"
    assert out["category"] == "관광"
    assert out["added_by"] == "u1"

def test_can_edit_item_author():
    item = {"added_by": "u1"}
    assert L.can_edit_item(item, "u1", "member") is True

def test_can_edit_item_owner():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", "owner") is True

def test_can_edit_item_other_member_denied():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", "member") is False

def test_can_edit_item_non_member_denied():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", None) is False
