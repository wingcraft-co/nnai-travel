"""tests/test_travel_service.py — 여행 추천/일정 서비스 로직 테스트 (fastapi/openai 불필요)"""
import pytest
from api import travel_service as S


def _profile(**over):
    base = {
        "travel_month": 1, "nights": 5, "budget_krw": 2000000,
        "interests": ["휴양", "자연"], "persona": "힐링 휴양러",
        "preferred_regions": ["동남아"],
        "companions": {"type": "친구그룹", "headcount": 3, "ages": ["성인"]},
        "language": "한국어",
    }
    base.update(over)
    return base


# ---------- build_recommend_response ----------

def test_recommend_returns_top_n():
    out = S.build_recommend_response(_profile(), top_n=5)
    assert len(out["top_destinations"]) == 5
    assert "notes" in out

def test_recommend_scores_descending():
    out = S.build_recommend_response(_profile(), top_n=5)
    scores = [c["score"] for c in out["top_destinations"]]
    assert scores == sorted(scores, reverse=True)

def test_recommend_respects_region():
    import travel_recommender as R
    out = S.build_recommend_response(_profile(preferred_regions=["동남아"]), top_n=5)
    for c in out["top_destinations"]:
        assert R._REGION_BY_COUNTRY.get(c["country_id"]) == "동남아"

def test_recommend_top_n_clamped_or_passed():
    out = S.build_recommend_response(_profile(), top_n=3)
    assert len(out["top_destinations"]) == 3


import json

_GOOD_ITIN = {
    "city": "Bali", "city_kr": "발리", "country_id": "ID",
    "trip_title": "발리 4박 5일 힐링 여행",
    "summary": "발리가 당신을 기다리고 있어요.",
    "days": [{"day": 1, "theme": "도착", "items": [
        {"time": "오후", "activity": "숙소 체크인", "category": "이동", "tip": "Grab"}]}],
    "packing_tips": ["여름옷"], "budget_estimate_krw": 1500000, "local_tips": ["현금 준비"],
}

def _dest():
    return {"city": "Bali", "city_kr": "발리", "country_id": "ID", "vibe": "휴양",
            "best_months": [5, 6, 7], "activities": ["해변"], "must_see": ["우붓"],
            "est_cost_krw": 1500000}

def _tprofile():
    return {"language": "한국어", "nights": 4, "travel_month": 7,
            "interests": ["휴양"], "persona": "힐링 휴양러",
            "companions": {"type": "커플(허니문)", "pace": "휴양 위주"}}


# ---------- build_itinerary_response ----------

def test_itinerary_uses_injected_llm_and_formats():
    captured = {}
    def fake_llm(messages):
        captured["messages"] = messages
        return json.dumps(_GOOD_ITIN, ensure_ascii=False)

    out = S.build_itinerary_response(_dest(), _tprofile(), llm_fn=fake_llm)
    # 프롬프트가 실제로 빌드되어 llm에 전달됨
    assert captured["messages"][0]["role"] == "system"
    assert "우붓" in captured["messages"][1]["content"]
    # 결과 포맷
    assert "발리 4박 5일 힐링 여행" in out["markdown"]
    assert "Day 1" in out["markdown"]
    assert out["itinerary"]["country_id"] == "ID"

def test_itinerary_injects_language():
    out = S.build_itinerary_response(
        _dest(), {**_tprofile(), "language": "English"},
        llm_fn=lambda m: json.dumps(_GOOD_ITIN, ensure_ascii=False),
    )
    assert out["itinerary"]["_language"] == "English"

def test_itinerary_error_raises_unavailable():
    with pytest.raises(S.ItineraryUnavailable):
        S.build_itinerary_response(_dest(), _tprofile(),
                                   llm_fn=lambda m: "ERROR: upstream timeout")
