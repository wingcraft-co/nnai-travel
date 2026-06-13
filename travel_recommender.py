"""travel_recommender.py — destinations.json 기반 여행지 추천 (규칙기반, 결정론적).

기존 이민용 recommender.py 와 독립적인 병렬 엔진. visa_db 미사용.
"""
from __future__ import annotations

import logging

from utils.destinations import load_destinations
from utils.travel_budget import estimate_trip_cost_krw, budget_fit_score

logger = logging.getLogger(__name__)

# country_id → 권역 (UI 선호 권역: 동남아/동북아/유럽/미주/중동·아프리카)
_REGION_BY_COUNTRY: dict[str, str] = {
    "MY": "동남아", "TH": "동남아", "ID": "동남아", "VN": "동남아", "PH": "동남아",
    "JP": "동북아", "TW": "동북아",
    "PT": "유럽", "EE": "유럽", "ES": "유럽", "DE": "유럽", "GR": "유럽",
    "CZ": "유럽", "HU": "유럽", "NL": "유럽", "AT": "유럽", "PL": "유럽",
    "IT": "유럽", "HR": "유럽", "RS": "유럽", "MK": "유럽", "CY": "유럽",
    "GE": "유럽", "TR": "유럽",
    "CR": "미주", "MX": "미주", "PE": "미주", "AR": "미주", "CO": "미주",
    "US": "미주", "PY": "미주",
    "MA": "중동/아프리카", "AE": "중동/아프리카", "QA": "중동/아프리카",
}

# 관심사 → (activity 키워드 집합, vibe 집합)
# 매칭: activity hit → +0.5, vibe hit → +0.5 (합산 상한 1.0 per interest)
_INTEREST_KEYWORDS: dict[str, tuple[set[str], set[str]]] = {
    "자연":   ({"트레킹", "자연", "전망", "서핑", "스노클링", "해변", "코끼리보호소"}, {"자연", "휴양"}),
    "미식":   ({"미식", "와인", "카페", "에그타르트", "야시장"}, {"감성"}),
    "액티비티": ({"서핑", "스노클링", "트레킹", "투어", "사막투어", "요가", "사막사파리"}, {"자연", "모험"}),
    "문화":   ({"사원", "도보관광", "미술관", "건축", "애니메이션", "왕궁"}, {"도시문화"}),
    "휴양":   ({"해변", "리조트", "온천", "요가", "마사지"}, {"휴양"}),
    "쇼핑":   ({"쇼핑"}, {"도시문화", "이국"}),
    "인생샷": ({"전망", "건축"}, {"감성", "이국"}),
}

# 여행 페르소나(퀴즈 결과) → 선호 vibe 집합
_PERSONA_VIBES: dict[str, set[str]] = {
    "액티브 탐험가": {"자연", "모험"},
    "힐링 휴양러":   {"휴양"},
    "미식 탐험가":   {"감성", "도시문화"},
    "문화 수집가":   {"도시문화", "감성"},
    "인생샷 헌터":   {"감성", "이국"},
}

_BLOCK_WEIGHTS: dict[str, float] = {
    "season": 0.25, "budget": 0.25, "interest": 0.25,
    "quality": 0.10, "companion": 0.15,
}


# ── 시즌 점수 ──────────────────────────────────────────────────

def _adjacent_months(months: list[int]) -> set[int]:
    adj: set[int] = set()
    for m in months:
        adj.add(m % 12 + 1)          # 다음 달
        adj.add((m - 2) % 12 + 1)    # 이전 달
    return adj


def season_score(dest: dict, month: int | None) -> float:
    """방문 월이 best_months에 들면 10, 인접 월 7, 그 외 4. 월 미입력=중립 6."""
    if not month:
        return 6.0
    best = dest.get("best_months") or []
    if month in best:
        return 10.0
    if month in _adjacent_months(best):
        return 7.0
    return 4.0


# ── 관심사/성향 점수 ──────────────────────────────────────────

def interest_score(dest: dict, interests: list[str], persona: str = "") -> float:
    """관심사 매치 비율(0~10) + 페르소나 vibe 보너스(+1.5, 상한 10).

    각 관심사마다: activity 키워드 hit → +0.5, vibe hit → +0.5 (최대 1.0).
    전체 평균 * 10.0 = base score.
    """
    activities = set(dest.get("activities") or [])
    vibe = dest.get("vibe") or ""
    if not interests:
        base = 6.0
    else:
        total = 0.0
        for it in interests:
            kw, vibes = _INTEREST_KEYWORDS.get(it, (set(), set()))
            hit = 0.0
            if activities & kw:
                hit += 0.5
            if vibe in vibes:
                hit += 0.5
            total += min(1.0, hit)
        base = total / len(interests) * 10.0
    if persona:
        if vibe in _PERSONA_VIBES.get(persona, set()):
            base = min(10.0, base + 1.5)
    return round(base, 3)


# ── 안전품질 점수 ─────────────────────────────────────────────

def quality_score(dest: dict) -> float:
    """안전(0.6) + 접근성(0.4) 기본 품질 점수."""
    safety = dest.get("safety", 5)
    access = dest.get("accessibility_score", 5)
    return round(min(10.0, safety * 0.6 + access * 0.4), 3)
