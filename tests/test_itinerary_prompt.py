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
