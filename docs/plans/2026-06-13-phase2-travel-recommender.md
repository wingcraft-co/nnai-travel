# Phase 2 — 여행 추천엔진 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1의 `destinations.json`을 입력으로, 여행 기간·예산·관심사·여행 성향·동행 프로필을 반영해 운명의 여행지 TOP-N을 결정론적으로 추천하는 규칙기반 엔진을 신설한다.

**Architecture:** 기존 이민용 `recommender.py`(visa_db 강결합, 4-블록)는 손대지 않고, `destinations.json` 로더(Phase 1) 위에 **새 `travel_recommender.py`**를 병렬 신설한다. 점수는 5개 블록(시즌·예산·관심사/성향·안전품질·동행)의 가중합이며, 권역 필터(소프트 폴백)와 접근성 하드 필터를 둔다. 비용 추정은 순수 함수 모듈 `utils/travel_budget.py`로 분리해 네트워크 없이 결정론적으로 테스트한다.

**Tech Stack:** Python 3, pytest. 외부 의존성 없음(환율은 고정 fallback 상수 사용). 테스트 실행은 `SKIP_EXTERNAL_INIT=1 python3 -m pytest`.

---

## 격리/원칙 (필수)

- 기존 `recommender.py`, `visa_db.json`, 이민 파이프라인은 **변경 금지**. 신규 파일만 추가한다.
- push는 항상 `develop`. `main` 금지.
- 새 테스트 파일은 `.github/workflows/main-tests.yml`에 등록(Task 5).
- 작업 로그는 루트 `tasklist.md`에 날짜별 2줄(Task 5).
- 엔드포인트/DB 변경 없음 → `cowork/backend/*` 동기화 불필요(이 Phase 한정).

## 입력/출력 계약

`recommend_destinations(profile, top_n=5, debug=False)` 의 `profile` dict:

```python
{
  "travel_month": 7,                 # 1~12, 없으면 None → 시즌 중립
  "nights": 4,                       # N박
  "budget_krw": 1500000,             # 1인 총예산(원), 0/None → 예산 중립
  "interests": ["휴양", "미식"],      # 다중, 없으면 중립
  "persona": "힐링 휴양러",           # 퀴즈 결과, 없으면 보너스 없음
  "preferred_regions": ["동남아"],    # 다중, [] 또는 "무관" → 전체
  "companions": {                     # 없으면 솔로 중립
    "type": "가족",
    "headcount": 4,
    "ages": ["유아", "성인"],
    "accessibility": ["없음"],
    "pace": "여유롭게 적당히"
  }
}
```

반환:

```python
{
  "top_destinations": [
    {"id": "DPS", "city": "...", "city_kr": "...", "country": "...", "country_id": "...",
     "vibe": "...", "budget_tier": "...", "best_months": [...], "peak_season": "...",
     "avg_flight_hours_from_icn": 7.0, "activities": [...], "must_see": [...],
     "monthly_cost_usd": 1200, "est_cost_krw": 1234000, "score": 8.4,
     "reasons": [{"point": "..."}]}
  ],
  "notes": ["...완화 안내..."]   # 폴백 발생 시
}
```

## File Structure

- `utils/travel_budget.py` (Create) — 비용 추정 순수 함수: `estimate_flight_usd`, `estimate_daily_usd`, `estimate_trip_cost_krw`, `budget_fit_score`. 책임: 결정론적 경비 산출(네트워크 없음).
- `travel_recommender.py` (Create, repo 루트) — 권역 매핑, 5개 블록 점수 함수, 하드/소프트 필터, `score_destination`, `recommend_destinations`. 책임: 랭킹/조립.
- `tests/test_travel_budget.py` (Create) — 비용/예산 단위 테스트.
- `tests/test_travel_recommender.py` (Create) — 블록 단위 + destinations.json 통합 테스트.
- `.github/workflows/main-tests.yml` (Modify) — 두 테스트 파일 등록.
- `tasklist.md` (Modify) — 2026-06-13 로그 추가.

각 블록 함수는 독립 순수 함수로 분리해 한 번에 컨텍스트에 담기게 한다. 국가 중복 제거는 하지 않는다(같은 나라 두 도시 노출 허용 — 여행에서는 바람직).

---

### Task 1: 여행 비용 추정 모듈 (`utils/travel_budget.py`)

**Files:**
- Create: `utils/travel_budget.py`
- Test: `tests/test_travel_budget.py`

- [ ] **Step 1: 실패 테스트 작성**

Create `tests/test_travel_budget.py`:

```python
"""tests/test_travel_budget.py — 여행 비용 추정 단위 테스트"""
from utils import travel_budget as B


def _dest(cost=1200, hours=7.0):
    return {"monthly_cost_usd": cost, "avg_flight_hours_from_icn": hours}


def test_flight_usd_increases_with_hours():
    assert B.estimate_flight_usd(1.5) < B.estimate_flight_usd(7.0) < B.estimate_flight_usd(14.0)

def test_flight_usd_positive():
    assert B.estimate_flight_usd(0.0) > 0

def test_daily_usd_from_monthly():
    # 1500/30 = 50, *1.4 관광보정 = 70.0
    assert B.estimate_daily_usd(1500) == 70.0

def test_trip_cost_krw_known_value():
    # flight = round(120 + 7.0*75) = 645, daily = 1200/30*1.4 = 56.0
    # total_usd = 645 + 56*4 = 869, *1400 = 1216600
    cost = B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=4)
    assert cost == 1216600

def test_trip_cost_krw_zero_nights():
    # nights=0 → 항공료만
    cost = B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=0)
    assert cost == round(645 * 1400)

def test_trip_cost_krw_clamps_negative_nights():
    assert B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=-3) == B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=0)

def test_budget_fit_no_budget_is_neutral():
    assert B.budget_fit_score(999999, 0) == 6.0

def test_budget_fit_thresholds():
    # ratio = est/budget
    assert B.budget_fit_score(50, 100) == 8.0    # 0.5 → 저렴
    assert B.budget_fit_score(80, 100) == 10.0   # 0.8 → 최적
    assert B.budget_fit_score(100, 100) == 10.0  # 1.0 경계
    assert B.budget_fit_score(110, 100) == 6.0   # 1.1 약간 초과
    assert B.budget_fit_score(140, 100) == 3.0   # 1.4 초과
    assert B.budget_fit_score(200, 100) == 1.0   # 2.0 대폭 초과
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_budget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.travel_budget'`

- [ ] **Step 3: 모듈 구현**

Create `utils/travel_budget.py`:

```python
"""utils/travel_budget.py — 여행 비용 추정 (순수 함수, 결정론적).

환율은 네트워크 없이 결정론적 테스트를 위해 고정 fallback 상수를 사용한다.
실제 환율 반영이 필요하면 호출부에서 usd_krw 인자로 주입한다.
"""
from __future__ import annotations

USD_KRW_FALLBACK = 1400


def estimate_flight_usd(flight_hours: float) -> int:
    """ICN 출발 왕복 항공료 근사(USD). 비행시간 기반 선형 추정."""
    return round(120 + flight_hours * 75)


def estimate_daily_usd(monthly_cost_usd: int) -> float:
    """월 생활비 → 1일 여행 경비 근사. 관광 보정 1.4배."""
    return monthly_cost_usd / 30.0 * 1.4


def estimate_trip_cost_krw(
    dest: dict, nights: int, headcount: int = 1,
    usd_krw: float = USD_KRW_FALLBACK,
) -> int:
    """1인 기준 총 여행비(KRW) 추정.

    예산은 spec상 '1인 총액'이므로 headcount는 1인 단가에 영향을 주지 않는다
    (동행 인원은 동행 블록에서만 활용). 시그니처는 호출 호환성을 위해 유지한다.
    """
    nights = max(0, nights)
    flight = estimate_flight_usd(dest["avg_flight_hours_from_icn"])
    daily = estimate_daily_usd(dest["monthly_cost_usd"])
    total_usd = flight + daily * nights
    return round(total_usd * usd_krw)


def budget_fit_score(est_krw: int, budget_krw: int) -> float:
    """예산 적합도 0~10. 예산 내가 최적, 초과 시 단계적 감점. 예산 미입력=중립."""
    if budget_krw <= 0:
        return 6.0
    ratio = est_krw / budget_krw
    if ratio <= 0.6:
        return 8.0
    if ratio <= 1.0:
        return 10.0
    if ratio <= 1.2:
        return 6.0
    if ratio <= 1.5:
        return 3.0
    return 1.0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_budget.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add utils/travel_budget.py tests/test_travel_budget.py
git commit -m "feat(recommender): 여행 비용/예산 추정 순수 함수 모듈

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 점수 블록 — 시즌 / 관심사·성향 / 안전품질 (`travel_recommender.py`)

**Files:**
- Create: `travel_recommender.py`
- Test: `tests/test_travel_recommender.py`

- [ ] **Step 1: 실패 테스트 작성**

Create `tests/test_travel_recommender.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'travel_recommender'`

- [ ] **Step 3: 모듈 + 블록 구현**

Create `travel_recommender.py`:

```python
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
_INTEREST_KEYWORDS: dict[str, tuple[set[str], set[str]]] = {
    "자연":   ({"트레킹", "자연", "전망", "서핑", "스노클링", "해변", "코끼리보호소"}, {"자연", "휴양"}),
    "미식":   ({"미식", "와인", "카페", "에그타르트", "야시장"}, {"감성", "도시문화"}),
    "액티비티": ({"서핑", "스노클링", "트레킹", "투어", "사막투어", "요가", "사막사파리"}, {"자연", "모험"}),
    "문화":   ({"사원", "도보관광", "미술관", "건축", "애니메이션", "왕궁"}, {"도시문화", "감성"}),
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
    """관심사 매치 비율(0~10) + 페르소나 vibe 보너스(+1.5, 상한 10)."""
    activities = set(dest.get("activities") or [])
    vibe = dest.get("vibe") or ""
    if not interests:
        base = 6.0
    else:
        matched = 0
        for it in interests:
            kw, vibes = _INTEREST_KEYWORDS.get(it, (set(), set()))
            if activities & kw or vibe in vibes:
                matched += 1
        base = matched / len(interests) * 10.0
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py -v`
Expected: PASS (11 passed — 시즌5 + 관심사5 + 품질1)

- [ ] **Step 5: 커밋**

```bash
git add travel_recommender.py tests/test_travel_recommender.py
git commit -m "feat(recommender): 여행 시즌·관심사·안전품질 점수 블록

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 동행 블록 + 접근성/권역 필터

**Files:**
- Modify: `travel_recommender.py` (블록 함수 추가)
- Test: `tests/test_travel_recommender.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가**

Append to `tests/test_travel_recommender.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py -v`
Expected: FAIL — `AttributeError: module 'travel_recommender' has no attribute 'companion_score'`

- [ ] **Step 3: 블록/필터 구현**

Append to `travel_recommender.py`:

```python
# ── 동행 블록 ─────────────────────────────────────────────────

_CHILD_AGES = {"유아", "초등", "청소년"}


def companion_score(dest: dict, companions: dict | None) -> float:
    """동행 구성별 적합도(0~10). 유형에 맞는 목적지 신호를 선택해 평가."""
    if not companions:
        return 6.0
    ctype = companions.get("type") or ""
    ages = companions.get("ages") or []
    flight = dest.get("avg_flight_hours_from_icn", 8)
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
        if flight > 8:
            score -= 1.5
    elif "효도" in ctype or has_senior:
        score = (access + safety) / 2
        if flight > 10:
            score -= 1.5
    elif "친구" in ctype:
        score = nightlife
    elif "회사" in ctype or "단체" in ctype:
        score = (access + nightlife) / 2
    else:  # 혼자 등
        score = 6.0
    return round(max(0.0, min(10.0, score)), 3)


# ── 하드/소프트 필터 ─────────────────────────────────────────

def passes_accessibility(dest: dict, companions: dict | None) -> bool:
    """휠체어 니즈가 있으면 접근성 5 미만 목적지를 하드 제외."""
    if not companions:
        return True
    needs = companions.get("accessibility") or []
    if "휠체어" in needs and dest.get("accessibility_score", 5) < 5:
        return False
    return True


def passes_region(dest: dict, preferred_regions: list[str]) -> bool:
    """선호 권역 필터. 빈 리스트 또는 '무관' 포함 시 전체 통과."""
    if not preferred_regions or "무관" in preferred_regions:
        return True
    region = _REGION_BY_COUNTRY.get(dest.get("country_id", ""), "")
    return region in preferred_regions
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py -v`
Expected: PASS (24 passed 누적 — 이전 11 + 동행6 + 접근성3 + 권역4)

- [ ] **Step 5: 커밋**

```bash
git add travel_recommender.py tests/test_travel_recommender.py
git commit -m "feat(recommender): 동행 블록 + 접근성/권역 필터

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 조립 — `score_destination` + `recommend_destinations` + 통합 테스트

**Files:**
- Modify: `travel_recommender.py`
- Test: `tests/test_travel_recommender.py`

- [ ] **Step 1: 실패 테스트 추가**

Append to `tests/test_travel_recommender.py`:

```python
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
    for c in out["top_destinations"]:
        from utils.destinations import get_destination
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py -k "score_destination or recommend" -v`
Expected: FAIL — `AttributeError: module 'travel_recommender' has no attribute 'score_destination'`

- [ ] **Step 3: 조립 함수 구현**

Append to `travel_recommender.py`:

```python
# ── 합성 점수 + 추천 ─────────────────────────────────────────

def score_destination(dest: dict, profile: dict) -> dict:
    """단일 목적지의 블록별 점수 + 가중합 + 예상 경비 반환."""
    month = profile.get("travel_month")
    interests = profile.get("interests") or []
    persona = profile.get("persona") or ""
    budget_krw = int(profile.get("budget_krw") or 0)
    nights = int(profile.get("nights") or 0)
    companions = profile.get("companions")
    headcount = int((companions or {}).get("headcount") or 1)

    s = season_score(dest, month)
    est = estimate_trip_cost_krw(dest, nights, headcount)
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
```

- [ ] **Step 4: 전체 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_recommender.py tests/test_travel_budget.py -v`
Expected: PASS (travel_recommender 32 + travel_budget 8 = 40 passed)

- [ ] **Step 5: 커밋**

```bash
git add travel_recommender.py tests/test_travel_recommender.py
git commit -m "feat(recommender): 합성 점수 + recommend_destinations 조립 + 통합 테스트

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CI 등록 + 작업 로그

**Files:**
- Modify: `.github/workflows/main-tests.yml`
- Modify: `tasklist.md`

- [ ] **Step 1: CI에 테스트 등록**

In `.github/workflows/main-tests.yml`, the test list has lines like `tests/test_destinations.py \`. Add the two new files right after `tests/test_destinations.py \`:

```yaml
            tests/test_destinations.py \
            tests/test_travel_budget.py \
            tests/test_travel_recommender.py \
```

- [ ] **Step 2: 작업 로그 추가**

In `tasklist.md`, under the existing `## 2026-06-13` section, append two lines:

```markdown
- Phase 2 완료: `travel_recommender.py`(시즌·예산·관심사/성향·안전품질·동행 5블록 가중합 + 권역 소프트폴백 + 접근성 하드필터)와 `utils/travel_budget.py`(결정론적 경비/예산 추정) 신설. 기존 이민용 recommender.py는 미변경.
- 여행 추천엔진 테스트 40개(비용 8 + 엔진 32) 통과 + CI 등록. destinations.json 기반 결정론적 랭킹.
```

- [ ] **Step 3: 전체 데이터/추천 테스트 회귀**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_destinations.py tests/test_travel_budget.py tests/test_travel_recommender.py -q`
Expected: PASS (22 + 8 + 32 = 62 passed)

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/main-tests.yml tasklist.md
git commit -m "chore: 여행 추천엔진 테스트 CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- spec "추천엔진 교체 → 여행 적합도(시즌매칭·예산핏·성향매칭·인기/안전) + 동행 프로필 블록" → Task 2(시즌·관심사/성향·안전품질) + Task 1(예산핏) + Task 3(동행) ✅
- spec 동행 신호 반영(아이→키즈/안전/짧은 비행, 허니문→로맨틱, 효도→접근성, 친구→나이트라이프, 접근성 니즈→하드필터/감점) → Task 3 `companion_score` + `passes_accessibility` ✅
- spec 입력(여행기간/예산/관심사/선호권역/성향/동행) → `profile` 계약에 모두 반영 ✅
- spec "Phase 2 DB 불필요" → 전부 JSON/순수함수 ✅
- spec 결정론적 테스트 → 환율 고정 상수, destinations.json 고정 입력 ✅

**2. Placeholder scan:** 모든 step에 실제 코드/명령/기대출력 포함. TBD/TODO 없음. ✅

**3. Type consistency:**
- `score_destination` 반환 키(season/budget/interest/quality/companion/est_cost_krw/total)가 `_build_reasons`·debug payload·테스트와 일치 ✅
- `estimate_trip_cost_krw(dest, nights, headcount=1)` 시그니처가 Task 1 정의와 Task 4 호출에서 동일 ✅
- `_REGION_BY_COUNTRY`/`_BLOCK_WEIGHTS`를 테스트가 `R._REGION_BY_COUNTRY`/`R._BLOCK_WEIGHTS`로 참조 — 모듈 전역으로 정의됨 ✅
- 블록 함수명(season_score/interest_score/quality_score/companion_score/passes_accessibility/passes_region)이 정의·테스트·조립에서 일관 ✅

**4. 테스트 합계:** 엔진 = Task2(시즌5+관심사5+품질1=11) + Task3(동행6+접근성3+권역4=13) + Task4(합성1+추천7=8) = **32**. 비용 = **8**. Phase 2 합 **40**. CI 회귀(+destinations 22) = **62**. 본문 Step 기대치는 이 집계에 맞춤. 실행 시 실제 수집 개수를 기준으로 판단하고, 불일치하면 테스트 누락을 의심한다.
