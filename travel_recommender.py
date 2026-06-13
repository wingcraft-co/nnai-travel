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
    "액티비티": ({"서핑", "스노클링", "트레킹", "투어", "사막투어", "요가"}, {"자연"}),
    "문화":   ({"사원", "도보관광", "미술관", "건축", "애니메이션", "도시관광"}, {"도시문화"}),
    "휴양":   ({"해변", "리조트", "온천", "요가", "마사지"}, {"휴양"}),
    "쇼핑":   ({"쇼핑"}, {"도시문화", "이국"}),
    "인생샷": ({"전망", "건축"}, {"감성", "이국"}),
}

# 여행 페르소나(퀴즈 결과) → 선호 vibe 집합
_PERSONA_VIBES: dict[str, set[str]] = {
    "액티브 탐험가": {"자연"},
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


# ── 동행 블록 ─────────────────────────────────────────────────

_CHILD_AGES = {"유아", "초등", "청소년"}

_KID_MAX_FLIGHT_HOURS = 8
_SENIOR_MAX_FLIGHT_HOURS = 10
_LONG_FLIGHT_PENALTY = 1.5


def companion_score(dest: dict, companions: dict | None) -> float:
    """동행 구성별 적합도(0~10). 유형에 맞는 목적지 신호를 선택해 평가."""
    if not companions:
        return 6.0
    ctype = companions.get("type") or ""
    ages = companions.get("ages") or []
    flight = dest.get("avg_flight_hours_from_icn", 0)
    kid = dest.get("kid_friendly", 5)
    romantic = dest.get("romantic", 5)
    access = dest.get("accessibility_score", 5)
    nightlife = dest.get("nightlife", 5)
    safety = dest.get("safety", 5)

    has_kid = any(a in _CHILD_AGES for a in ages)
    has_senior = "60대+" in ages

    if "커플" in ctype or "허니문" in ctype:
        score = romantic
    elif "가족" in ctype and has_kid:
        score = (kid + safety) / 2
        if flight > _KID_MAX_FLIGHT_HOURS:
            score -= _LONG_FLIGHT_PENALTY
    elif "효도" in ctype or has_senior:
        score = (access + safety) / 2
        if flight > _SENIOR_MAX_FLIGHT_HOURS:
            score -= _LONG_FLIGHT_PENALTY
    elif "친구" in ctype:
        score = nightlife
    elif "회사" in ctype or "단체" in ctype:
        score = (access + nightlife) / 2
    elif "가족" in ctype:
        # 성인 가족(아이·고령자 없음): 안전+편의 중심
        score = (safety + access) / 2
    else:  # 혼자 등
        score = 6.0
    return round(max(0.0, min(10.0, score)), 3)


# ── 하드/소프트 필터 ─────────────────────────────────────────

def passes_accessibility(dest: dict, companions: dict | None) -> bool:
    """휠체어 니즈가 있으면 접근성 5 미만 목적지를 하드 제외."""
    if not companions:
        return True
    needs = companions.get("accessibility") or []
    if "휠체어" in needs and dest.get("accessibility_score", 0) < 5:
        return False
    return True


def passes_region(dest: dict, preferred_regions: list[str]) -> bool:
    """선호 권역 필터. 빈 리스트 또는 '무관' 포함 시 전체 통과."""
    if not preferred_regions or "무관" in preferred_regions:
        return True
    region = _REGION_BY_COUNTRY.get(dest.get("country_id", ""), "")
    return region in preferred_regions


# ── 합성 점수 + 추천 ─────────────────────────────────────────

def score_destination(dest: dict, profile: dict) -> dict:
    """단일 목적지의 블록별 점수 + 가중합 + 예상 경비 반환."""
    month = profile.get("travel_month")
    interests = profile.get("interests") or []
    persona = profile.get("persona") or ""
    budget_krw = int(profile.get("budget_krw") or 0)
    nights = int(profile.get("nights") or 0)
    companions = profile.get("companions")

    s = season_score(dest, month)
    est = estimate_trip_cost_krw(dest, nights)
    b = budget_fit_score(est, budget_krw)
    i = interest_score(dest, interests, persona)
    q = quality_score(dest)
    c = companion_score(dest, companions)

    w = _BLOCK_WEIGHTS
    total = (s * w["season"] + b * w["budget"] + i * w["interest"]
             + q * w["quality"] + c * w["companion"])
    return {
        "season": round(s, 3), "budget": round(b, 3), "interest": round(i, 3),
        "quality": round(q, 3), "companion": round(c, 3),
        "est_cost_krw": est, "total": round(min(10.0, max(0.0, total)), 2),
    }


def _build_reasons(dest: dict, br: dict, profile: dict) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    if br["season"] >= 9:
        reasons.append({"point": f"{profile.get('travel_month')}월은 {dest['city_kr']} 여행 적기입니다."})
    if br["budget"] >= 9 and int(profile.get("budget_krw") or 0) > 0:
        reasons.append({"point": "예상 경비가 예산에 잘 맞습니다."})
    if br["interest"] >= 7:
        reasons.append({"point": "관심사와 맞는 액티비티가 풍부합니다."})
    if br["companion"] >= 8:
        reasons.append({"point": "동행 구성에 잘 맞는 분위기입니다."})
    if not reasons:
        reasons.append({"point": "현재 조건에서 종합 점수가 가장 높습니다."})
    return reasons[:3]


def _build_notes(region_relaxed: bool, access_relaxed: bool) -> list[str]:
    notes: list[str] = []
    if region_relaxed:
        notes.append("선호 권역만으로는 후보가 부족해 권역 조건을 완화했습니다.")
    if access_relaxed:
        notes.append("접근성 조건을 만족하는 후보가 부족해 일부 완화했습니다.")
    return notes


def recommend_destinations(profile: dict, top_n: int = 5, debug: bool = False) -> dict:
    """destinations.json 전체를 점수화해 상위 top_n 추천. 국가 중복 제거 없음."""
    dests = load_destinations()
    preferred = profile.get("preferred_regions") or []
    companions = profile.get("companions")

    def collect(region_filter: bool, access_filter: bool):
        rows = []
        for d in dests:
            if region_filter and not passes_region(d, preferred):
                continue
            if access_filter and not passes_accessibility(d, companions):
                continue
            br = score_destination(d, profile)
            rows.append((br["total"], d, br))
        return rows

    rows = collect(region_filter=True, access_filter=True)
    region_relaxed = False
    access_relaxed = False
    if len(rows) < top_n:
        rows = collect(region_filter=False, access_filter=True)
        region_relaxed = True
    if len(rows) < top_n:
        rows = collect(region_filter=False, access_filter=False)
        access_relaxed = True

    rows.sort(key=lambda x: x[0], reverse=True)
    top = rows[:top_n]

    cards: list[dict] = []
    for _score, d, br in top:
        cards.append({
            "id": d["id"], "city": d["city"], "city_kr": d["city_kr"],
            "country": d["country"], "country_id": d["country_id"],
            "vibe": d["vibe"], "budget_tier": d["budget_tier"],
            "best_months": d["best_months"], "peak_season": d["peak_season"],
            "avg_flight_hours_from_icn": d["avg_flight_hours_from_icn"],
            "activities": d["activities"], "must_see": d["must_see"],
            "monthly_cost_usd": d["monthly_cost_usd"],
            "est_cost_krw": br["est_cost_krw"], "score": br["total"],
            "reasons": _build_reasons(d, br, profile),
        })

    result = {
        "top_destinations": cards,
        "notes": _build_notes(region_relaxed, access_relaxed),
    }
    logger.info("[recommend_destinations] top_n=%d returned=%d region_relaxed=%s access_relaxed=%s",
                top_n, len(cards), region_relaxed, access_relaxed)
    if debug:
        result["debug"] = {
            "weights": _BLOCK_WEIGHTS,
            "scored": [{"id": d["id"], **br} for _s, d, br in top],
        }
    return result
