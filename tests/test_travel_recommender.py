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


# ---------- 동행 블록 ----------

def test_companion_none_is_neutral():
    assert R.companion_score(_dest(), None) == 6.0

def test_companion_solo_is_neutral():
    assert R.companion_score(_dest(), {"type": "혼자"}) == 6.0

def test_companion_couple_uses_romantic():
    assert R.companion_score(_dest(romantic=9), {"type": "커플(허니문)"}) == 9.0

def test_companion_family_kids_penalizes_long_flight():
    near = R.companion_score(_dest(kid_friendly=8, safety=8, avg_flight_hours_from_icn=5.0),
                             {"type": "가족", "ages": ["유아"]})
    far = R.companion_score(_dest(kid_friendly=8, safety=8, avg_flight_hours_from_icn=14.0),
                            {"type": "가족", "ages": ["유아"]})
    assert near == 8.0          # (8+8)/2
    assert far == 6.5           # (8+8)/2 - 1.5

def test_companion_senior_uses_accessibility():
    s = R.companion_score(_dest(accessibility_score=9, safety=7, avg_flight_hours_from_icn=5.0),
                          {"type": "효도여행", "ages": ["60대+"]})
    assert s == 8.0             # (9+7)/2

def test_companion_friends_uses_nightlife():
    assert R.companion_score(_dest(nightlife=9), {"type": "친구그룹"}) == 9.0


# ---------- 접근성 하드 필터 ----------

def test_accessibility_no_companion_passes():
    assert R.passes_accessibility(_dest(accessibility_score=3), None) is True

def test_accessibility_wheelchair_excludes_low():
    assert R.passes_accessibility(_dest(accessibility_score=4),
                                  {"accessibility": ["휠체어"]}) is False
    assert R.passes_accessibility(_dest(accessibility_score=6),
                                  {"accessibility": ["휠체어"]}) is True

def test_accessibility_none_need_passes():
    assert R.passes_accessibility(_dest(accessibility_score=3),
                                  {"accessibility": ["없음"]}) is True


# ---------- 권역 필터 ----------

def test_region_empty_passes_all():
    assert R.passes_region(_dest(country_id="TH"), []) is True

def test_region_muyeon_passes_all():
    assert R.passes_region(_dest(country_id="TH"), ["무관"]) is True

def test_region_match():
    assert R.passes_region(_dest(country_id="TH"), ["동남아"]) is True
    assert R.passes_region(_dest(country_id="JP"), ["동남아"]) is False

def test_region_unknown_country_excluded_when_filtered():
    assert R.passes_region(_dest(country_id="ZZ"), ["동남아"]) is False


def test_companion_family_adults_only_uses_safety_access():
    # 아이·고령자 없는 성인 가족 → (safety+access)/2, 혼자 fallback 아님
    s = R.companion_score(_dest(safety=8, accessibility_score=6),
                          {"type": "가족", "ages": ["성인"]})
    assert s == 7.0

def test_companion_group_uses_access_and_nightlife():
    s = R.companion_score(_dest(accessibility_score=6, nightlife=8),
                          {"type": "회사/단체"})
    assert s == 7.0

def test_companion_kid_penalty_boundary_no_penalty_at_threshold():
    # flight == 8 은 임계값(>8)에 걸리지 않아 감점 없음
    s = R.companion_score(_dest(kid_friendly=8, safety=8, avg_flight_hours_from_icn=8.0),
                          {"type": "가족", "ages": ["유아"]})
    assert s == 8.0


# ---------- 합성 점수 ----------

def test_score_destination_returns_breakdown():
    profile = {"travel_month": 12, "nights": 4, "budget_krw": 1500000,
               "interests": ["휴양"], "persona": "힐링 휴양러",
               "companions": {"type": "커플(허니문)"}}
    br = R.score_destination(_dest(best_months=[11, 12, 1]), profile)
    for k in ("season", "budget", "interest", "quality", "companion", "est_cost_krw", "total"):
        assert k in br
    assert 0.0 <= br["total"] <= 10.0
    assert br["season"] == 10.0


# ---------- recommend_destinations 통합 ----------

@pytest.fixture
def beach_profile():
    return {
        "travel_month": 1, "nights": 5, "budget_krw": 2000000,
        "interests": ["휴양", "자연"], "persona": "힐링 휴양러",
        "preferred_regions": ["동남아"],
        "companions": {"type": "친구그룹", "headcount": 3, "ages": ["성인"]},
    }

def test_recommend_returns_top_n(beach_profile):
    out = R.recommend_destinations(beach_profile, top_n=5)
    assert len(out["top_destinations"]) == 5

def test_recommend_scores_descending(beach_profile):
    out = R.recommend_destinations(beach_profile, top_n=5)
    scores = [c["score"] for c in out["top_destinations"]]
    assert scores == sorted(scores, reverse=True)

def test_recommend_respects_region(beach_profile):
    out = R.recommend_destinations(beach_profile, top_n=5)
    for c in out["top_destinations"]:
        assert R._REGION_BY_COUNTRY.get(c["country_id"]) == "동남아"

def test_recommend_card_shape(beach_profile):
    out = R.recommend_destinations(beach_profile, top_n=3)
    c = out["top_destinations"][0]
    for k in ("id", "city", "city_kr", "country", "country_id", "vibe",
              "budget_tier", "best_months", "must_see", "est_cost_krw",
              "score", "reasons"):
        assert k in c
    assert c["reasons"]

def test_recommend_wheelchair_excludes_low_access():
    profile = {"travel_month": None, "nights": 4, "budget_krw": 0,
               "interests": [], "preferred_regions": [],
               "companions": {"type": "가족", "accessibility": ["휠체어"]}}
    out = R.recommend_destinations(profile, top_n=10)
    from utils.destinations import get_destination
    for c in out["top_destinations"]:
        assert get_destination(c["id"])["accessibility_score"] >= 5

def test_recommend_region_relaxed_note():
    # 미주만 선호하지만 top_n이 커서 권역 완화 발생 → notes 채워짐
    profile = {"travel_month": None, "nights": 3, "budget_krw": 0,
               "interests": [], "preferred_regions": ["미주"]}
    out = R.recommend_destinations(profile, top_n=50)
    assert any("권역" in n for n in out["notes"])

def test_recommend_debug_payload(beach_profile):
    out = R.recommend_destinations(beach_profile, top_n=3, debug=True)
    assert "debug" in out
    assert out["debug"]["weights"] == R._BLOCK_WEIGHTS
