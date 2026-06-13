"""tests/test_travel_recommender.py — 여행 추천엔진 테스트"""
import pytest
import travel_recommender as R


def _dest(**over):
    base = {
        "id": "XX", "city": "Test", "city_kr": "테스트", "country": "Testland",
        "country_id": "TH", "monthly_cost_usd": 1200, "avg_flight_hours_from_icn": 6.0,
        "best_months": [11, 12, 1, 2], "peak_season": "건기", "budget_tier": "low",
        "activities": ["해변", "미식", "스노클링"], "vibe": "휴양", "must_see": ["A"],
        "safety": 7, "kid_friendly": 7, "romantic": 8, "accessibility_score": 6,
        "nightlife": 7,
    }
    base.update(over)
    return base


# ---------- 시즌 점수 ----------

def test_season_match_is_high():
    assert R.season_score(_dest(best_months=[7, 8]), 7) == 10.0

def test_season_adjacent_is_mid():
    assert R.season_score(_dest(best_months=[7]), 6) == 7.0
    assert R.season_score(_dest(best_months=[7]), 8) == 7.0

def test_season_off_is_low():
    assert R.season_score(_dest(best_months=[7]), 1) == 4.0

def test_season_no_month_is_neutral():
    assert R.season_score(_dest(), None) == 6.0

def test_season_adjacent_wraps_year():
    # best=1월 → 인접 12월/2월
    assert R.season_score(_dest(best_months=[1]), 12) == 7.0


# ---------- 관심사/성향 점수 ----------

def test_interest_full_match():
    d = _dest(activities=["해변", "리조트"], vibe="휴양")
    assert R.interest_score(d, ["휴양"]) == 10.0

def test_interest_partial_match():
    d = _dest(activities=["사원", "도보관광"], vibe="도시문화")
    # 문화 매치, 미식 불일치 → 1/2 * 10 = 5.0
    assert R.interest_score(d, ["문화", "미식"]) == 5.0

def test_interest_empty_is_neutral():
    assert R.interest_score(_dest(), []) == 6.0

def test_interest_persona_bonus():
    d = _dest(activities=["해변"], vibe="휴양")
    base = R.interest_score(d, ["휴양"])
    with_persona = R.interest_score(d, ["휴양"], persona="힐링 휴양러")
    assert with_persona >= base  # 보너스(상한 10 클램프)

def test_interest_persona_bonus_lifts_partial():
    d = _dest(activities=["사원"], vibe="감성")
    # 문화만 부분매치(5.0) + 인생샷 헌터 vibe 감성 보너스(+1.5) = 6.5
    assert R.interest_score(d, ["문화"], persona="인생샷 헌터") == 6.5


# ---------- 안전품질 점수 ----------

def test_quality_score_weighted():
    # safety 8 * 0.6 + access 6 * 0.4 = 4.8 + 2.4 = 7.2
    assert R.quality_score(_dest(safety=8, accessibility_score=6)) == 7.2
