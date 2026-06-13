# Phase 1: 여행 목적지 데이터 모델 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 52개 도시(`city_scores.json`)를 여행 도메인 스키마로 변환한 `destinations.json`과 그 로더/검증 모듈을 구축한다.

**Architecture:** 순수 파생 함수(`utils/destinations.py`)로 climate/cost 등 기존 필드에서 여행 필드를 결정적으로 derive하고, 큐레이션 CSV(`data/rawdata/destination_editorial.csv`)를 override 레이어로 둔다. 빌드 스크립트(`scripts/build_destinations.py`)가 둘을 합쳐 `destinations.json`(+ 프론트 복사본)을 생성한다. 모든 파생은 결정적이라 TDD 가능.

**Tech Stack:** Python 3, pytest, JSON/CSV. DB·LLM 미사용 (Phase 1은 순수 데이터).

**참고 사항:**
- spec: `docs/specs/2026-06-13-travel-pivot-design.md`
- 기존 데이터 테스트 컨벤션: `tests/test_city_scores.py`, `tests/test_data_schema.py`
- 테스트 실행: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -v`
- Phase 1은 DB/API 변경 없음 → `cowork/backend/db-schema.md`, `api-reference.md` 수정 불필요

---

## File Structure

| 파일 | 책임 |
|------|------|
| `utils/destinations.py` (생성) | 스키마 상수, 순수 파생 함수, `validate_destination`, `load_destinations`, `get_destination` |
| `data/rawdata/destination_editorial.csv` (생성) | 큐레이션 override 레이어 (best_months/activities/vibe/must_see/scores) |
| `scripts/build_destinations.py` (생성) | city_scores + editorial → `destinations.json` (+ 프론트 복사본) 생성, 항공시간 상수 |
| `data/destinations.json` (생성, 스크립트 산출물) | 런타임 canonical 여행 목적지 데이터 |
| `frontend/src/data/destinations.json` (생성, 스크립트 산출물) | 프론트 enrichment용 복사본 |
| `tests/test_destinations.py` (생성) | 파생 함수 단위 테스트 + 생성 파일 통합 테스트 |
| `.github/workflows/main-tests.yml` (수정) | 새 테스트 등록 |
| `tasklist.md` (수정) | 작업 로그 |

---

## Task 1: 순수 파생 함수 + 스키마 상수 (`utils/destinations.py`)

**Files:**
- Create: `utils/destinations.py`
- Test: `tests/test_destinations.py`

- [ ] **Step 1: 파생 함수 단위 테스트 작성**

`tests/test_destinations.py` 생성:

```python
"""tests/test_destinations.py — 여행 목적지 데이터 모델 테스트"""
import json
from pathlib import Path
import pytest
from utils.data_paths import resolve_data_path
from utils import destinations as D


# ---------- 순수 파생 함수 단위 테스트 ----------

def test_budget_tier_thresholds():
    assert D.derive_budget_tier(800) == "low"
    assert D.derive_budget_tier(1499) == "low"
    assert D.derive_budget_tier(1500) == "mid"
    assert D.derive_budget_tier(2999) == "mid"
    assert D.derive_budget_tier(3000) == "high"
    assert D.derive_budget_tier(4500) == "high"

def test_best_months_tropical():
    assert D.derive_best_months("tropical") == [11, 12, 1, 2, 3]

def test_best_months_unknown_climate_fallback():
    assert D.derive_best_months("no-such-climate") == [4, 5, 9, 10]

def test_vibe_by_climate():
    assert D.derive_vibe("tropical") == "휴양"
    assert D.derive_vibe("mediterranean") == "감성"
    assert D.derive_vibe("no-such-climate") == "도시문화"

def test_activities_non_empty():
    assert D.derive_activities("tropical")
    assert D.derive_activities("no-such-climate")

def test_kid_friendly_average():
    assert D.derive_kid_friendly(8, 6) == 7
    assert D.derive_kid_friendly(4, 4) == 4
    assert D.derive_kid_friendly(10, 10) == 10

def test_romantic_by_climate():
    assert D.derive_romantic("tropical") == 8
    assert D.derive_romantic("mediterranean") == 8
    assert D.derive_romantic("continental") == 6

def test_nightlife_by_community():
    assert D.derive_nightlife("large") == 8
    assert D.derive_nightlife("medium") == 6
    assert D.derive_nightlife("small") == 4

def test_accessibility_tiers():
    assert D.derive_accessibility("JP") == 8
    assert D.derive_accessibility("TH") == 6
    assert D.derive_accessibility("XX") == 4
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.destinations'`

- [ ] **Step 3: `utils/destinations.py` 작성 (상수 + 파생 함수)**

```python
"""utils/destinations.py — 여행 목적지 데이터 스키마, 파생 함수, 로더/검증."""
import json
from utils.data_paths import resolve_data_path

BUDGET_TIERS = ("low", "mid", "high")

_CLIMATE_BEST_MONTHS = {
    "tropical": [11, 12, 1, 2, 3],
    "subtropical": [3, 4, 5, 10, 11],
    "mediterranean": [5, 6, 9, 10],
    "continental": [5, 6, 9],
    "temperate": [4, 5, 9, 10],
    "maritime": [6, 7, 8, 9],
    "highland": [4, 5, 9, 10, 11],
    "desert": [11, 12, 1, 2, 3],
    "semi-arid": [3, 4, 5, 10, 11],
}
_CLIMATE_VIBE = {
    "tropical": "휴양", "subtropical": "휴양", "mediterranean": "감성",
    "continental": "도시문화", "temperate": "도시문화", "maritime": "도시문화",
    "highland": "자연", "desert": "이국", "semi-arid": "자연",
}
_CLIMATE_ACTIVITIES = {
    "tropical": ["해변", "스노클링", "리조트", "카페"],
    "subtropical": ["해변", "온천", "카페", "도보관광"],
    "mediterranean": ["해변", "미식", "도보관광", "와인"],
    "continental": ["도시관광", "미술관", "미식", "쇼핑"],
    "temperate": ["도시관광", "미술관", "미식", "쇼핑"],
    "maritime": ["도시관광", "미술관", "미식", "쇼핑"],
    "highland": ["트레킹", "자연", "전망"],
    "desert": ["사막투어", "럭셔리", "쇼핑"],
    "semi-arid": ["트레킹", "자연", "전망"],
}
_CLIMATE_PEAK = {
    "tropical": "11~3월 건기", "subtropical": "봄·가을", "mediterranean": "5~10월 성수기",
    "continental": "여름 성수기", "temperate": "봄·가을", "maritime": "여름",
    "highland": "건기", "desert": "겨울", "semi-arid": "봄·가을",
}
_NIGHTLIFE_BY_COMMUNITY = {"large": 8, "medium": 6, "small": 4}
_ROMANTIC_CLIMATES = {"tropical", "subtropical", "mediterranean"}

_DEVELOPED_COUNTRIES = {
    "PT", "ES", "DE", "EE", "GR", "NL", "AT", "CZ", "HU", "PL",
    "IT", "HR", "JP", "TW", "AE", "QA", "CY", "US",
}
_MID_COUNTRIES = {
    "TH", "MY", "VN", "ID", "PH", "GE", "TR", "RS", "MK", "ME",
    "MA", "CR", "MX", "AR", "UY", "PE", "CO", "SI", "BG", "RO", "AL",
}


def derive_budget_tier(monthly_cost_usd: int) -> str:
    if monthly_cost_usd < 1500:
        return "low"
    if monthly_cost_usd < 3000:
        return "mid"
    return "high"


def derive_best_months(climate: str) -> list[int]:
    return list(_CLIMATE_BEST_MONTHS.get(climate, [4, 5, 9, 10]))


def derive_vibe(climate: str) -> str:
    return _CLIMATE_VIBE.get(climate, "도시문화")


def derive_activities(climate: str) -> list[str]:
    return list(_CLIMATE_ACTIVITIES.get(climate, ["도시관광", "미식"]))


def derive_peak_season(climate: str) -> str:
    return _CLIMATE_PEAK.get(climate, "봄·가을")


def _clamp(value: int, low: int = 1, high: int = 10) -> int:
    return max(low, min(high, value))


def derive_kid_friendly(safety_score: int, english_score: int) -> int:
    return _clamp(round((safety_score + english_score) / 2))


def derive_romantic(climate: str) -> int:
    return 8 if climate in _ROMANTIC_CLIMATES else 6


def derive_nightlife(community_size: str) -> int:
    return _NIGHTLIFE_BY_COMMUNITY.get(community_size, 5)


def derive_accessibility(country_id: str) -> int:
    if country_id in _DEVELOPED_COUNTRIES:
        return 8
    if country_id in _MID_COUNTRIES:
        return 6
    return 4
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -v`
Expected: PASS (9 passed) — 파생 함수 테스트만 (통합 테스트는 Task 4에서 추가)

- [ ] **Step 5: 커밋**

```bash
git add utils/destinations.py tests/test_destinations.py
git commit -m "feat(data): 여행 목적지 파생 함수 + 스키마 상수 추가"
```

---

## Task 2: 검증 함수 `validate_destination` (`utils/destinations.py`)

**Files:**
- Modify: `utils/destinations.py`
- Test: `tests/test_destinations.py`

- [ ] **Step 1: 검증 함수 테스트 추가**

`tests/test_destinations.py`에 추가 (파일 끝):

```python
# ---------- validate_destination 단위 테스트 ----------

def _minimal_dest() -> dict:
    return {
        "id": "XX", "city": "Test", "city_kr": "테스트", "country": "Testland",
        "country_id": "XX", "monthly_cost_usd": 1500, "internet_mbps": 100,
        "english_score": 7, "climate": "tropical", "safety_score": 7,
        "best_months": [11, 12, 1], "peak_season": "건기",
        "avg_flight_hours_from_icn": 6.0, "budget_tier": "mid",
        "activities": ["해변"], "vibe": "휴양", "safety": 7,
        "kid_friendly": 7, "romantic": 8, "accessibility_score": 6,
        "nightlife": 6, "must_see": [], "curated": False,
    }

def test_validate_passes_good():
    assert D.validate_destination(_minimal_dest()) == []

def test_validate_catches_missing_field():
    bad = _minimal_dest()
    del bad["vibe"]
    errs = D.validate_destination(bad)
    assert any("누락" in e for e in errs)

def test_validate_catches_bad_budget_tier():
    bad = _minimal_dest()
    bad["budget_tier"] = "cheap"
    errs = D.validate_destination(bad)
    assert any("budget_tier" in e for e in errs)

def test_validate_catches_bad_month():
    bad = _minimal_dest()
    bad["best_months"] = [13]
    errs = D.validate_destination(bad)
    assert any("best_months" in e for e in errs)

def test_validate_catches_out_of_range_score():
    bad = _minimal_dest()
    bad["nightlife"] = 11
    errs = D.validate_destination(bad)
    assert any("nightlife" in e for e in errs)

def test_validate_catches_empty_activities():
    bad = _minimal_dest()
    bad["activities"] = []
    errs = D.validate_destination(bad)
    assert any("activities" in e for e in errs)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -k validate -v`
Expected: FAIL — `AttributeError: module 'utils.destinations' has no attribute 'validate_destination'`

- [ ] **Step 3: `validate_destination` 구현 (`utils/destinations.py` 끝에 추가)**

```python
REQUIRED_FIELDS = {
    "id", "city", "city_kr", "country", "country_id", "monthly_cost_usd",
    "internet_mbps", "english_score", "climate", "safety_score", "best_months",
    "peak_season", "avg_flight_hours_from_icn", "budget_tier", "activities",
    "vibe", "safety", "kid_friendly", "romantic", "accessibility_score",
    "nightlife", "must_see", "curated",
}
SCORE_FIELDS = ("safety", "kid_friendly", "romantic", "accessibility_score", "nightlife")


def validate_destination(d: dict) -> list[str]:
    """destination dict의 유효성 검사. 오류 메시지 리스트 반환 (빈 리스트=정상)."""
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(d.keys())
    if missing:
        errors.append(f"누락 필드: {sorted(missing)}")
        return errors
    if d["budget_tier"] not in BUDGET_TIERS:
        errors.append(f"budget_tier 잘못됨: {d['budget_tier']}")
    if not d["best_months"] or any(m < 1 or m > 12 for m in d["best_months"]):
        errors.append(f"best_months 범위 오류: {d['best_months']}")
    if d["avg_flight_hours_from_icn"] <= 0:
        errors.append("avg_flight_hours_from_icn 양수여야 함")
    for field in SCORE_FIELDS:
        if not (1 <= d[field] <= 10):
            errors.append(f"{field} 1~10 범위 벗어남: {d[field]}")
    if not isinstance(d["activities"], list) or not d["activities"]:
        errors.append("activities 비어있음")
    return errors
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -k validate -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add utils/destinations.py tests/test_destinations.py
git commit -m "feat(data): validate_destination 검증 함수 추가"
```

---

## Task 3: 큐레이션 editorial CSV 시드 (`data/rawdata/destination_editorial.csv`)

**Files:**
- Create: `data/rawdata/destination_editorial.csv`

- [ ] **Step 1: CSV 작성**

리스트 필드는 파이프(`|`) 구분. 빈 칸은 빌드 시 파생값으로 대체. 헤더 + 큐레이션 10개 도시:

```csv
id,best_months,activities,vibe,must_see,kid_friendly,romantic,accessibility_score,nightlife
DPS,5|6|7|8|9,해변|서핑|요가|사원,휴양,우붓|짱구|울루와뚜사원,6,9,5,7
LIS,4|5|6|9|10,도보관광|미식|에그타르트|전망,감성,벨렘탑|알파마|신트라,7,8,8,7
BKK,11|12|1|2,사원|미식|야시장|마사지,도시문화,왕궁|왓아룬|짜뚜짝마켓,6,6,6,9
CNX,11|12|1|2,사원|트레킹|카페|코끼리보호소,자연,도이수텝|올드시티|선데이마켓,7,7,5,5
TYO,3|4|10|11,도시관광|미식|쇼핑|애니메이션,도시문화,시부야|아사쿠사|디즈니랜드,8,7,9,8
OSA,3|4|10|11,미식|도시관광|테마파크|쇼핑,도시문화,도톤보리|오사카성|유니버설스튜디오,8,7,9,8
DAD,2|3|4|5,해변|리조트|미식|투어,휴양,미케비치|바나힐|호이안,7,8,5,6
BCN,5|6|9|10,해변|건축|미식|도보관광,감성,사그라다파밀리아|구엘공원|람블라스,7,8,8,8
DXB,11|12|1|2|3,쇼핑|사막투어|럭셔리|전망,이국,부르즈할리파|두바이몰|사막사파리,8,7,9,7
HKT,11|12|1|2|3,해변|스노클링|리조트|나이트라이프,휴양,파통비치|피피섬|빅부다,7,8,6,8
```

- [ ] **Step 2: CSV 파싱 검증 (수동)**

Run: `python3 -c "import csv; rows=list(csv.DictReader(open('data/rawdata/destination_editorial.csv', encoding='utf-8'))); print(len(rows), 'rows'); print(rows[0])"`
Expected: `10 rows` 출력, 첫 행에 id=DPS 와 9개 컬럼 표시

- [ ] **Step 3: 커밋**

```bash
git add data/rawdata/destination_editorial.csv
git commit -m "feat(data): 여행 목적지 큐레이션 editorial CSV 시드 (10개 도시)"
```

---

## Task 4: 빌드 스크립트 + 생성 + 로더 통합 테스트

**Files:**
- Create: `scripts/build_destinations.py`
- Modify: `utils/destinations.py` (로더 추가)
- Create (산출물): `data/destinations.json`, `frontend/src/data/destinations.json`
- Test: `tests/test_destinations.py`

- [ ] **Step 1: 빌드 스크립트 작성 (`scripts/build_destinations.py`)**

`FLIGHT_HOURS_FROM_ICN`은 52개 도시 전부 포함 (인천 출발 근사 비행시간, 단위: 시간):

```python
"""scripts/build_destinations.py — city_scores.json + editorial CSV → destinations.json.

실행: python -m scripts.build_destinations   (repo 루트에서)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from utils.data_paths import resolve_data_path
from utils.destinations import (
    derive_budget_tier, derive_best_months, derive_vibe, derive_activities,
    derive_peak_season, derive_kid_friendly, derive_romantic, derive_nightlife,
    derive_accessibility, validate_destination,
)

ROOT = Path(__file__).parent.parent
EDITORIAL_CSV = ROOT / "data" / "rawdata" / "destination_editorial.csv"
FRONTEND_COPY = ROOT / "frontend" / "src" / "data" / "destinations.json"

# 인천(ICN) 출발 근사 직항/환승 비행시간 (시간). 큐레이션 상수.
FLIGHT_HOURS_FROM_ICN = {
    "KL": 6.5, "PG": 6.5, "LIS": 14.5, "PTO": 15.0, "CNX": 6.0, "BKK": 6.0,
    "TLL": 11.0, "BCN": 13.5, "MAD": 14.5, "DPS": 7.0, "BLN": 11.0, "TBS": 11.0,
    "SJO": 18.0, "SJD": 14.0, "ATH": 12.0, "HER": 13.0, "MNL": 4.0, "CEU": 5.0,
    "HAN": 5.0, "SGN": 5.5, "VLC": 14.0, "PRG": 11.0, "BUD": 11.0, "AMS": 11.0,
    "VIE": 11.0, "WAW": 10.5, "KRK": 11.0, "MUC": 11.0, "MIL": 12.5, "DBV": 13.0,
    "BEG": 11.5, "SKP": 12.0, "NIC": 12.0, "IST": 11.5, "CEI": 7.0, "USM": 7.0,
    "OSA": 1.5, "TYO": 2.5, "FUK": 1.5, "MEX": 14.5, "OAX": 16.0, "LIM": 20.0,
    "EZE": 24.0, "MDE": 19.0, "MIA": 15.5, "RAK": 16.0, "DXB": 9.5, "DAD": 5.0,
    "TPE": 2.5, "HKT": 7.0, "ASU": 25.0, "DOH": 10.0,
}


def _load_editorial() -> dict[str, dict]:
    if not EDITORIAL_CSV.exists():
        return {}
    with open(EDITORIAL_CSV, encoding="utf-8") as f:
        return {row["id"].strip(): row for row in csv.DictReader(f)}


def _split(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split("|") if x.strip()]


def _split_months(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(x) for x in raw.split("|") if x.strip().isdigit()]


def _ed_int(ed: dict, key: str, fallback: int) -> int:
    raw = ed.get(key)
    if raw is not None and str(raw).strip().isdigit():
        return int(raw)
    return fallback


def build() -> list[dict]:
    cities = json.loads(resolve_data_path("city_scores.json").read_text(encoding="utf-8"))["cities"]
    editorial = _load_editorial()
    dests: list[dict] = []
    for c in cities:
        cid = c["id"]
        climate = c.get("climate", "")
        ed = editorial.get(cid, {})
        if cid not in FLIGHT_HOURS_FROM_ICN:
            raise ValueError(f"{cid}: FLIGHT_HOURS_FROM_ICN 에 비행시간 없음")
        d = {
            "id": cid,
            "city": c["city"],
            "city_kr": c["city_kr"],
            "country": c["country"],
            "country_id": c["country_id"],
            "monthly_cost_usd": c["monthly_cost_usd"],
            "internet_mbps": c["internet_mbps"],
            "english_score": c["english_score"],
            "climate": climate,
            "safety_score": c["safety_score"],
            "best_months": _split_months(ed.get("best_months")) or derive_best_months(climate),
            "peak_season": ed.get("peak_season") or derive_peak_season(climate),
            "avg_flight_hours_from_icn": FLIGHT_HOURS_FROM_ICN[cid],
            "budget_tier": derive_budget_tier(c["monthly_cost_usd"]),
            "activities": _split(ed.get("activities")) or derive_activities(climate),
            "vibe": ed.get("vibe") or derive_vibe(climate),
            "safety": round(c["safety_score"]),
            "kid_friendly": _ed_int(ed, "kid_friendly", derive_kid_friendly(c["safety_score"], c["english_score"])),
            "romantic": _ed_int(ed, "romantic", derive_romantic(climate)),
            "accessibility_score": _ed_int(ed, "accessibility_score", derive_accessibility(c["country_id"])),
            "nightlife": _ed_int(ed, "nightlife", derive_nightlife(c.get("community_size", "medium"))),
            "must_see": _split(ed.get("must_see")),
            "curated": cid in editorial,
        }
        errs = validate_destination(d)
        if errs:
            raise ValueError(f"{cid} 검증 실패: {errs}")
        dests.append(d)
    return dests


def main() -> None:
    dests = build()
    payload = {"destinations": dests}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    out = resolve_data_path("destinations.json")
    out.write_text(text, encoding="utf-8")
    FRONTEND_COPY.write_text(text, encoding="utf-8")
    curated = sum(1 for d in dests if d["curated"])
    print(f"wrote {len(dests)} destinations ({curated} curated) → {out}")
    print(f"  frontend copy → {FRONTEND_COPY}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 빌드 실행**

Run: `python -m scripts.build_destinations`
Expected: `wrote 52 destinations (10 curated) → .../data/destinations.json` 출력, 에러 없음

- [ ] **Step 3: 로더 함수 통합 테스트 추가**

`tests/test_destinations.py` 끝에 추가:

```python
# ---------- 생성된 destinations.json 통합 테스트 ----------

@pytest.fixture(scope="module")
def dests():
    return D.load_destinations()

def test_count_52(dests):
    assert len(dests) == 52

def test_all_pass_validation(dests):
    for d in dests:
        errs = D.validate_destination(d)
        assert errs == [], f"{d['id']}: {errs}"

def test_ids_match_city_scores(dests):
    cs = json.loads(resolve_data_path("city_scores.json").read_text(encoding="utf-8"))["cities"]
    assert {d["id"] for d in dests} == {c["id"] for c in cs}

def test_curated_cities_flagged(dests):
    by_id = {d["id"]: d for d in dests}
    assert by_id["DPS"]["curated"] is True
    assert by_id["DPS"]["must_see"]  # 큐레이션 도시는 must_see 채워짐

def test_get_destination_found():
    d = D.get_destination("BKK")
    assert d is not None and d["id"] == "BKK"

def test_get_destination_missing():
    assert D.get_destination("ZZZ") is None

def test_frontend_copy_in_sync():
    backend = json.loads(resolve_data_path("destinations.json").read_text(encoding="utf-8"))
    fe_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "destinations.json"
    frontend = json.loads(fe_path.read_text(encoding="utf-8"))
    assert backend == frontend
```

- [ ] **Step 4: 로더 함수 구현 (`utils/destinations.py` 끝에 추가)**

```python
_DEST_CACHE: list[dict] | None = None


def load_destinations() -> list[dict]:
    """destinations.json 로드 (모듈 캐시)."""
    global _DEST_CACHE
    if _DEST_CACHE is None:
        path = resolve_data_path("destinations.json")
        with open(path, encoding="utf-8") as f:
            _DEST_CACHE = json.load(f)["destinations"]
    return _DEST_CACHE


def get_destination(dest_id: str) -> dict | None:
    """id로 목적지 조회. 없으면 None."""
    return next((d for d in load_destinations() if d["id"] == dest_id), None)
```

- [ ] **Step 5: 전체 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py -v`
Expected: PASS (전체 통과 — 파생 9 + 검증 6 + 통합 7)

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_destinations.py utils/destinations.py tests/test_destinations.py data/destinations.json frontend/src/data/destinations.json
git commit -m "feat(data): destinations.json 빌드 스크립트 + 로더 + 통합 테스트"
```

---

## Task 5: CI 등록 + 작업 로그

**Files:**
- Modify: `.github/workflows/main-tests.yml`
- Modify: `tasklist.md`

- [ ] **Step 1: CI 테스트 목록에 등록**

`.github/workflows/main-tests.yml`에서 `tests/test_data_schema.py \` 줄 바로 아래에 추가:

```yaml
            tests/test_destinations.py \
```

- [ ] **Step 2: CI 로컬 모사 — 전체 데이터 테스트 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 .venv/bin/pytest tests/test_destinations.py tests/test_city_scores.py tests/test_data_schema.py -q`
Expected: 전부 PASS

- [ ] **Step 3: tasklist.md 작업 로그 추가**

`tasklist.md` 상단(또는 날짜 순서에 맞는 위치)에 추가:

```markdown
## 2026-06-13
- Phase 1(데이터 모델): 기존 52개 도시를 여행 도메인 스키마(destinations.json)로 변환.
  climate/cost 기반 결정적 파생 + editorial CSV override 레이어. 로더/검증/빌드 스크립트 + 테스트 22건.
```

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/main-tests.yml tasklist.md
git commit -m "test: destinations 테스트 CI 등록 + 작업 로그"
```

---

## Self-Review (작성자 확인 완료)

**Spec coverage:** spec의 "Phase 1: 데이터 모델 — destinations.json 여행 스키마 + 52개 도시 여행/동행 필드 + sync 스크립트" 전 항목 커버. 동행 매칭 필드(kid_friendly/romantic/accessibility_score/nightlife) 포함. DB/API 변경 없음(JSON only)이므로 db-schema/api-reference 동기화는 정당하게 제외.

**Placeholder scan:** "적절한 검증 추가" 류 추상 단계 없음. 모든 코드 단계에 실제 코드 포함. FLIGHT_HOURS_FROM_ICN 52개 전부 명시.

**Type consistency:** 파생 함수 시그니처(Task1) ↔ 빌드 스크립트 호출(Task4) 일치. REQUIRED_FIELDS(Task2)의 23개 필드 ↔ 빌드 스크립트 산출 dict 키 일치 확인. `validate_destination`/`load_destinations`/`get_destination` 명칭 일관.

**범위:** Phase 1만 다룸. 추천엔진(Phase 2)·프롬프트(Phase 3)는 별도 plan.
