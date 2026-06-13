"""tests/test_itinerary_prompt.py — 여행 일정 프롬프트 빌더 테스트"""
from prompts import itinerary as I


# ---------- nights_to_label ----------

def test_nights_label_ko():
    assert I.nights_to_label(4) == "4박 5일"
    assert I.nights_to_label(1) == "1박 2일"

def test_nights_label_day_trip():
    assert I.nights_to_label(0) == "당일치기"
    assert I.nights_to_label(-2) == "당일치기"

def test_nights_label_en():
    assert I.nights_to_label(4, "English") == "4 nights 5 days"
    assert I.nights_to_label(0, "English") == "day trip"


# ---------- pace_instruction ----------

def test_pace_instruction_known():
    assert "4~5" in I.pace_instruction("빡빡하게 많이")
    assert "1~2" in I.pace_instruction("휴양 위주")

def test_pace_instruction_default():
    # 미지정 → 빈 문자열 아님(기본 안내 제공)
    assert I.pace_instruction("") != ""


# ---------- companion_instruction ----------

def test_companion_couple():
    assert "로맨틱" in I.companion_instruction({"type": "커플(허니문)"})

def test_companion_family_with_kids():
    s = I.companion_instruction({"type": "가족", "ages": ["유아"]})
    assert "키즈" in s or "휴식" in s

def test_companion_senior():
    s = I.companion_instruction({"type": "효도여행", "ages": ["60대+"]})
    assert "완만" in s or "휴식" in s

def test_companion_none_is_empty():
    assert I.companion_instruction(None) == ""
    assert I.companion_instruction({}) == ""


# ---------- interest_emphasis ----------

def test_interest_emphasis_lists_interests():
    s = I.interest_emphasis(["미식", "휴양"])
    assert "미식" in s and "휴양" in s

def test_interest_emphasis_empty():
    assert I.interest_emphasis([]) == ""


# ---------- build_itinerary_prompt ----------

def _dest():
    return {
        "city": "Bali", "city_kr": "발리", "country_id": "ID", "vibe": "휴양",
        "best_months": [5, 6, 7, 8, 9], "activities": ["해변", "서핑", "요가"],
        "must_see": ["우붓", "짱구", "울루와뚜사원"], "est_cost_krw": 1500000,
    }

def _profile(**over):
    base = {
        "language": "한국어", "nights": 4, "travel_month": 7,
        "interests": ["휴양", "자연"], "persona": "힐링 휴양러",
        "companions": {"type": "커플(허니문)", "pace": "휴양 위주"},
    }
    base.update(over)
    return base

def test_build_returns_two_messages():
    msgs = I.build_itinerary_prompt(_dest(), _profile())
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"

def test_build_system_is_korean_prompt():
    msgs = I.build_itinerary_prompt(_dest(), _profile())
    assert msgs[0]["content"] == I.ITINERARY_SYSTEM_PROMPT

def test_build_system_is_english_when_en():
    msgs = I.build_itinerary_prompt(_dest(), _profile(language="English"))
    assert msgs[0]["content"] == I.ITINERARY_SYSTEM_PROMPT_EN

def test_build_user_contains_nights_label():
    msgs = I.build_itinerary_prompt(_dest(), _profile(nights=4))
    assert "4박 5일" in msgs[1]["content"]

def test_build_user_contains_city_and_must_see():
    msgs = I.build_itinerary_prompt(_dest(), _profile())
    user = msgs[1]["content"]
    assert "Bali" in user
    assert "우붓" in user  # must_see 반영

def test_build_user_injects_companion_and_pace():
    msgs = I.build_itinerary_prompt(_dest(), _profile())
    user = msgs[1]["content"]
    assert "로맨틱" in user      # companion (커플)
    assert "1~2" in user          # pace (휴양 위주)

def test_build_user_injects_interests_and_month():
    msgs = I.build_itinerary_prompt(_dest(), _profile())
    user = msgs[1]["content"]
    assert "휴양" in user
    assert "7" in user            # travel_month

def test_build_handles_missing_companions():
    msgs = I.build_itinerary_prompt(_dest(), _profile(companions=None))
    assert msgs[1]["content"]  # 크래시 없이 생성
