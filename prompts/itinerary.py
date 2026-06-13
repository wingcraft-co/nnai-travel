"""prompts/itinerary.py — 여행 일정(N박M일) 프롬프트 빌더.

기존 이민용 prompts/builder.py 와 독립적인 병렬 모듈.
"""
from __future__ import annotations


def nights_to_label(nights: int, language: str = "한국어") -> str:
    """N박 → 'N박 M일' 라벨. 0 이하면 당일치기."""
    nights = max(0, int(nights))
    if language == "English":
        return "day trip" if nights == 0 else f"{nights} nights {nights + 1} days"
    return "당일치기" if nights == 0 else f"{nights}박 {nights + 1}일"


_PACE_INSTRUCTION = {
    "빡빡하게 많이":   "하루 4~5개 일정으로 알차게 채우세요.",
    "여유롭게 적당히": "하루 3개 내외 일정으로 여유 있게 구성하세요.",
    "휴양 위주":       "하루 1~2개 일정과 충분한 휴식·자유시간을 포함하세요.",
}
_PACE_INSTRUCTION_EN = {
    "빡빡하게 많이":   "Pack 4-5 activities per day.",
    "여유롭게 적당히": "Keep around 3 activities per day with breathing room.",
    "휴양 위주":       "Limit to 1-2 activities per day with ample rest and free time.",
}
_PACE_DEFAULT = "하루 3개 내외 일정으로 균형 있게 구성하세요."
_PACE_DEFAULT_EN = "Aim for a balanced ~3 activities per day."


def pace_instruction(pace: str, language: str = "한국어") -> str:
    """여행 페이스 → 하루 일정 밀도 지시. 미지정이면 기본 안내."""
    if language == "English":
        return _PACE_INSTRUCTION_EN.get(pace, _PACE_DEFAULT_EN)
    return _PACE_INSTRUCTION.get(pace, _PACE_DEFAULT)


_CHILD_AGES = {"유아", "초등", "청소년"}


def companion_instruction(companions: dict | None, language: str = "한국어") -> str:
    """동행 구성 → 일정 구성 지시 한 줄. 동행 정보 없으면 빈 문자열."""
    if not companions:
        return ""
    ctype = companions.get("type") or ""
    ages = companions.get("ages") or []
    has_kid = any(a in _CHILD_AGES for a in ages)
    has_senior = "60대+" in ages
    en = language == "English"

    if "커플" in ctype or "허니문" in ctype:
        return ("Include romantic dinners and private experiences."
                if en else "로맨틱한 디너와 프라이빗한 경험을 포함하세요.")
    if "가족" in ctype and has_kid:
        return ("Favor kid-friendly spots, minimize transit, and include afternoon rest."
                if en else "키즈프렌들리 장소와 이동 최소화, 오후 휴식 시간을 고려하세요.")
    if "효도" in ctype or has_senior:
        return ("Use gentle routes, frequent rest, and accessible venues."
                if en else "완만한 동선과 잦은 휴식, 접근성 좋은 장소 위주로 구성하세요.")
    if "친구" in ctype:
        return ("Include nightlife and group activities."
                if en else "나이트라이프와 그룹 액티비티를 포함하세요.")
    if "회사" in ctype or "단체" in ctype:
        return ("Include group-friendly logistics and a group dining spot."
                if en else "단체 이동이 수월한 동선과 회식 장소를 포함하세요.")
    if "가족" in ctype:
        return ("Balance comfort and shared experiences for an adult family."
                if en else "성인 가족이 함께 즐길 안전하고 편안한 일정으로 구성하세요.")
    return ("Include cafes, walks, and flexible solo-friendly plans."
            if en else "혼자 즐기기 좋은 카페·산책·자유로운 일정을 포함하세요.")


def interest_emphasis(interests: list[str], language: str = "한국어") -> str:
    """관심사 강조 지시. 빈 리스트면 빈 문자열."""
    if not interests:
        return ""
    joined = ", ".join(interests)
    if language == "English":
        return f"Prioritize activities matching the traveler's interests: {joined}."
    return f"여행자의 관심사({joined})에 맞는 활동을 우선 배치하세요."


_PERSONA_EMPHASIS = {
    "액티브 탐험가": "역동적인 액티비티와 탐험 중심으로 구성하세요.",
    "힐링 휴양러":   "휴식과 힐링 중심으로 느긋하게 구성하세요.",
    "미식 탐험가":   "현지 미식 경험을 일정의 중심에 두세요.",
    "문화 수집가":   "역사·문화·예술 명소를 충실히 담으세요.",
    "인생샷 헌터":   "포토 스팟과 감성적인 장소를 비중 있게 넣으세요.",
}
_PERSONA_EMPHASIS_EN = {
    "액티브 탐험가": "Center the plan on dynamic activities and exploration.",
    "힐링 휴양러":   "Center the plan on rest and slow healing.",
    "미식 탐험가":   "Make local food experiences the core of the plan.",
    "문화 수집가":   "Fill the plan with history, culture, and art landmarks.",
    "인생샷 헌터":   "Emphasize photo spots and aesthetic locations.",
}


def persona_emphasis(persona: str, language: str = "한국어") -> str:
    """여행 성향(퀴즈) 강조 지시. 없으면 빈 문자열."""
    if not persona:
        return ""
    if language == "English":
        return _PERSONA_EMPHASIS_EN.get(persona, "")
    return _PERSONA_EMPHASIS.get(persona, "")
