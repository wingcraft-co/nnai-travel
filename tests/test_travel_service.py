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
