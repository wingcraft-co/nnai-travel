"""tests/test_itinerary_parser.py — 일정 응답 파싱/렌더링 테스트"""
import json
from api import itinerary_parser as P


_GOOD = {
    "city": "Bali", "city_kr": "발리", "country_id": "ID",
    "trip_title": "발리 4박 5일 힐링 여행",
    "summary": "발리가 당신을 기다리고 있어요.",
    "days": [
        {"day": 1, "theme": "도착", "items": [
            {"time": "오후", "activity": "숙소 체크인", "category": "이동", "tip": "Grab 이용"}]},
        {"day": 2, "theme": "해변", "items": [
            {"time": "오전", "activity": "짱구 해변", "category": "관광", "tip": "선셋 추천"}]},
    ],
    "packing_tips": ["여름옷", "선크림"],
    "budget_estimate_krw": 1500000,
    "local_tips": ["현금 준비", "사롱 착용"],
}


# ---------- parse_itinerary ----------

def test_parse_plain_json():
    out = P.parse_itinerary(json.dumps(_GOOD, ensure_ascii=False))
    assert out["city"] == "Bali"
    assert len(out["days"]) == 2

def test_parse_code_fenced_json():
    raw = "```json\n" + json.dumps(_GOOD, ensure_ascii=False) + "\n```"
    out = P.parse_itinerary(raw)
    assert out["trip_title"] == "발리 4박 5일 힐링 여행"

def test_parse_json_with_surrounding_text():
    raw = "여기 일정입니다:\n" + json.dumps(_GOOD, ensure_ascii=False) + "\n감사합니다."
    out = P.parse_itinerary(raw)
    assert out["country_id"] == "ID"

def test_parse_failure_returns_fallback():
    out = P.parse_itinerary("완전히 깨진 응답 — JSON 없음")
    assert out["days"] == []
    assert "_raw" in out
