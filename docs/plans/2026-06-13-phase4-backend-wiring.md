# Phase 4 (백엔드 배선) — 여행 추천·일정 엔드포인트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 2 추천엔진(`travel_recommender`)과 Phase 3 일정 플래너(`prompts/itinerary`, `api/itinerary_parser`)를 실제 HTTP 엔드포인트(`POST /api/travel/recommend`, `POST /api/travel/itinerary`)로 노출한다. 기존 이민용 엔드포인트는 그대로 두고 병렬 신설한다.

**Architecture:** 핵심 로직은 **순수 서비스 레이어** `api/travel_service.py`에 두고(LLM 호출 함수는 주입 가능 — 로컬 결정론적 테스트), 얇은 FastAPI 라우터 `api/travel.py`가 요청 검증·에러 매핑만 담당한다. 라우터는 `server.py`에 `include_router(prefix="/api/travel")`로 연결한다. 로컬 테스트 환경에는 `fastapi`/`openai`가 없으므로(CI에는 있음) 서비스 테스트는 로컬에서 돌고, 라우터 테스트는 `pytest.importorskip("fastapi")`로 CI에서만 실행된다.

**Tech Stack:** FastAPI(APIRouter), Pydantic, pytest. LLM은 `api/hf_client.query_model`(주입). 테스트는 `SKIP_EXTERNAL_INIT=1 python3 -m pytest`.

---

## 격리/원칙 (필수)

- 기존 `/api/recommend`, `/api/reveal`, `/api/detail`, `app.py`, `recommender.py`, `prompts/builder.py`, `api/parser.py`는 **변경 금지**.
- `server.py`는 import 2줄 + `include_router` 1줄만 추가(엔드포인트 로직은 라우터에).
- push는 항상 `develop`. `main` 금지.
- **CLAUDE.md 규칙**: 엔드포인트 추가 → `cowork/backend/api-reference.md` 동기화(Task 4). DB 변경 없음 → db-schema.md 동기화 불필요.
- 새 테스트 파일은 `.github/workflows/main-tests.yml`에 등록(Task 4). 작업 로그 `tasklist.md`(Task 4).

## 엔드포인트 계약

### POST /api/travel/recommend (LLM 없음, 결정론적)

Request:
```json
{
  "travel_month": 7,
  "nights": 4,
  "budget_krw": 2000000,
  "interests": ["휴양", "자연"],
  "persona": "힐링 휴양러",
  "preferred_regions": ["동남아"],
  "companions": {"type": "커플(허니문)", "headcount": 2, "ages": ["성인"], "accessibility": ["없음"], "pace": "휴양 위주"},
  "top_n": 5,
  "language": "한국어"
}
```

Response: `recommend_destinations`의 반환 그대로 — `{"top_destinations": [...], "notes": [...]}`.

### POST /api/travel/itinerary (LLM 호출)

Request:
```json
{
  "destination": {"city": "Bali", "city_kr": "발리", "country_id": "ID", "vibe": "휴양",
                  "best_months": [5,6,7,8,9], "activities": ["해변","서핑","요가"],
                  "must_see": ["우붓","짱구"], "est_cost_krw": 1500000},
  "travel_profile": {"language": "한국어", "nights": 4, "travel_month": 7,
                     "interests": ["휴양"], "persona": "힐링 휴양러",
                     "companions": {"type": "커플(허니문)", "pace": "휴양 위주"}}
}
```

Response: `{"markdown": "...일정 마크다운...", "itinerary": {...파싱된 일정 dict...}}`.
에러: `502` (LLM 불안정 — `query_model`이 `ERROR:`로 시작하는 응답 반환 시).

## File Structure

- `api/travel_service.py` (Create) — `build_recommend_response`, `build_itinerary_response`(llm 주입), `ItineraryUnavailable` 예외. fastapi/openai 미의존(openai는 런타임에만 lazy import). 책임: 도메인 로직.
- `api/travel.py` (Create) — APIRouter + Pydantic 요청 모델 2종. 책임: 검증·에러 매핑.
- `server.py` (Modify) — import + `include_router(travel_router, prefix="/api/travel")`.
- `tests/test_travel_service.py` (Create) — 서비스 로직 로컬 테스트(가짜 llm).
- `tests/test_travel_api.py` (Create) — 라우터 테스트(`importorskip("fastapi")`, CI 전용).
- `cowork/backend/api-reference.md` (Modify) — 신규 엔드포인트 문서.
- `.github/workflows/main-tests.yml` (Modify), `tasklist.md` (Modify).

---

### Task 1: 추천 서비스 (`build_recommend_response`)

**Files:**
- Create: `api/travel_service.py`
- Test: `tests/test_travel_service.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_travel_service.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.travel_service'`

- [ ] **Step 3: 서비스 구현** — Create `api/travel_service.py`:

```python
"""api/travel_service.py — 여행 추천/일정 도메인 로직 (FastAPI 비의존).

라우터(api/travel.py)가 호출하는 순수 서비스 레이어. LLM 호출 함수는 주입 가능하여
fastapi/openai 없이도 결정론적으로 테스트된다.
"""
from __future__ import annotations

from typing import Callable

from travel_recommender import recommend_destinations


class ItineraryUnavailable(Exception):
    """LLM이 일정 생성에 실패(ERROR 응답)했을 때 발생."""


def build_recommend_response(profile: dict, top_n: int = 5) -> dict:
    """여행 프로필 → 추천 결과 dict. LLM/DB 미사용, 결정론적."""
    return recommend_destinations(profile, top_n=top_n)


def build_itinerary_response(
    destination: dict,
    travel_profile: dict,
    llm_fn: Callable[[list[dict]], str] | None = None,
) -> dict:
    """선택 여행지 + 프로필 → {markdown, itinerary}. llm_fn 미지정 시 실서비스 호출."""
    from prompts.itinerary import build_itinerary_prompt
    from api.itinerary_parser import parse_itinerary, format_itinerary_markdown

    if llm_fn is None:
        from api.hf_client import query_model as llm_fn  # lazy: openai는 런타임에만

    messages = build_itinerary_prompt(destination, travel_profile)
    raw = llm_fn(messages)
    if isinstance(raw, str) and raw.startswith("ERROR:"):
        raise ItineraryUnavailable(raw)

    parsed = parse_itinerary(raw)
    parsed["_language"] = travel_profile.get("language", "한국어")
    return {"markdown": format_itinerary_markdown(parsed), "itinerary": parsed}
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_service.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/travel_service.py tests/test_travel_service.py
git commit -m "feat(travel-api): 추천 서비스 레이어 (build_recommend_response)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 일정 서비스 (`build_itinerary_response`) 테스트

**Files:**
- Modify: (구현은 Task 1에서 이미 작성됨) — 이 Task는 일정 서비스의 동작을 테스트로 고정한다.
- Test: `tests/test_travel_service.py`

- [ ] **Step 1: 실패 테스트 추가** — Append to `tests/test_travel_service.py`:

```python
import json

_GOOD_ITIN = {
    "city": "Bali", "city_kr": "발리", "country_id": "ID",
    "trip_title": "발리 4박 5일 힐링 여행",
    "summary": "발리가 당신을 기다리고 있어요.",
    "days": [{"day": 1, "theme": "도착", "items": [
        {"time": "오후", "activity": "숙소 체크인", "category": "이동", "tip": "Grab"}]}],
    "packing_tips": ["여름옷"], "budget_estimate_krw": 1500000, "local_tips": ["현금 준비"],
}

def _dest():
    return {"city": "Bali", "city_kr": "발리", "country_id": "ID", "vibe": "휴양",
            "best_months": [5, 6, 7], "activities": ["해변"], "must_see": ["우붓"],
            "est_cost_krw": 1500000}

def _tprofile():
    return {"language": "한국어", "nights": 4, "travel_month": 7,
            "interests": ["휴양"], "persona": "힐링 휴양러",
            "companions": {"type": "커플(허니문)", "pace": "휴양 위주"}}


# ---------- build_itinerary_response ----------

def test_itinerary_uses_injected_llm_and_formats():
    captured = {}
    def fake_llm(messages):
        captured["messages"] = messages
        return json.dumps(_GOOD_ITIN, ensure_ascii=False)

    out = S.build_itinerary_response(_dest(), _tprofile(), llm_fn=fake_llm)
    # 프롬프트가 실제로 빌드되어 llm에 전달됨
    assert captured["messages"][0]["role"] == "system"
    assert "우붓" in captured["messages"][1]["content"]
    # 결과 포맷
    assert "발리 4박 5일 힐링 여행" in out["markdown"]
    assert "Day 1" in out["markdown"]
    assert out["itinerary"]["country_id"] == "ID"

def test_itinerary_injects_language():
    out = S.build_itinerary_response(
        _dest(), {**_tprofile(), "language": "English"},
        llm_fn=lambda m: json.dumps(_GOOD_ITIN, ensure_ascii=False),
    )
    assert out["itinerary"]["_language"] == "English"

def test_itinerary_error_raises_unavailable():
    with pytest.raises(S.ItineraryUnavailable):
        S.build_itinerary_response(_dest(), _tprofile(),
                                   llm_fn=lambda m: "ERROR: upstream timeout")
```

- [ ] **Step 2: 통과 확인** (구현은 Task 1에 포함됨)

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_service.py -v`
Expected: PASS (4 + 3 = 7 passed)

만약 일정 테스트가 실패하면 Task 1에서 작성한 `build_itinerary_response`/`ItineraryUnavailable`를 위 구현과 대조하여 수정한다.

- [ ] **Step 3: 커밋**

```bash
git add tests/test_travel_service.py
git commit -m "test(travel-api): 일정 서비스 동작 고정 (주입 llm + 502 경로)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: FastAPI 라우터 + server.py 배선

**Files:**
- Create: `api/travel.py`
- Modify: `server.py`
- Test: `tests/test_travel_api.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_travel_api.py`:

```python
"""tests/test_travel_api.py — 여행 엔드포인트 라우터 테스트 (CI 전용; 로컬은 fastapi 부재 시 skip)"""
import json
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.travel as travel_mod


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(travel_mod.router, prefix="/api/travel")
    return TestClient(app)


def test_recommend_endpoint_returns_top_destinations():
    client = _client()
    resp = client.post("/api/travel/recommend", json={
        "travel_month": 1, "nights": 5, "budget_krw": 2000000,
        "interests": ["휴양"], "persona": "힐링 휴양러",
        "preferred_regions": ["동남아"], "top_n": 5,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["top_destinations"]) == 5
    assert "notes" in body


def test_recommend_endpoint_validates_top_n():
    client = _client()
    resp = client.post("/api/travel/recommend", json={"nights": 3, "top_n": 99})
    assert resp.status_code == 422  # top_n > 10


def test_itinerary_endpoint_returns_markdown(monkeypatch):
    good = {"city": "Bali", "city_kr": "발리", "country_id": "ID",
            "trip_title": "발리 여행", "summary": "s",
            "days": [{"day": 1, "theme": "t", "items": [
                {"time": "오전", "activity": "a", "category": "관광", "tip": "x"}]}],
            "packing_tips": [], "local_tips": []}
    monkeypatch.setattr(
        travel_mod, "build_itinerary_response",
        lambda destination, travel_profile: {"markdown": "# 발리 여행\n## Day 1", "itinerary": good},
    )
    client = _client()
    resp = client.post("/api/travel/itinerary", json={
        "destination": {"city": "Bali"}, "travel_profile": {"nights": 4},
    })
    assert resp.status_code == 200
    assert "Day 1" in resp.json()["markdown"]


def test_itinerary_endpoint_maps_unavailable_to_502(monkeypatch):
    def boom(destination, travel_profile):
        raise travel_mod.ItineraryUnavailable("ERROR: down")
    monkeypatch.setattr(travel_mod, "build_itinerary_response", boom)
    client = _client()
    resp = client.post("/api/travel/itinerary", json={
        "destination": {"city": "Bali"}, "travel_profile": {"nights": 4},
    })
    assert resp.status_code == 502
```

- [ ] **Step 2: 실패 확인 (CI 기준; 로컬은 skip 예상)**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_api.py -v`
Expected (로컬, fastapi 부재): `4 skipped` (importorskip). CI에서는 FAIL — `No module named 'api.travel'`.

- [ ] **Step 3: 라우터 구현** — Create `api/travel.py`:

```python
"""api/travel.py — 여행 추천/일정 FastAPI 라우터 (얇은 어댑터).

도메인 로직은 api/travel_service.py. 이 모듈은 검증·에러 매핑만 담당한다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.travel_service import (
    build_recommend_response,
    build_itinerary_response,
    ItineraryUnavailable,
)

router = APIRouter()


class CompanionsModel(BaseModel):
    type: str = Field(default="", max_length=50)
    headcount: int = Field(default=1, ge=1, le=50)
    ages: list[str] = Field(default_factory=list, max_length=10)
    accessibility: list[str] = Field(default_factory=list, max_length=10)
    pace: str = Field(default="", max_length=50)


class TravelRecommendRequest(BaseModel):
    travel_month: int | None = Field(default=None, ge=1, le=12)
    nights: int = Field(default=0, ge=0, le=60)
    budget_krw: int = Field(default=0, ge=0)
    interests: list[str] = Field(default_factory=list, max_length=10)
    persona: str = Field(default="", max_length=50)
    preferred_regions: list[str] = Field(default_factory=list, max_length=10)
    companions: CompanionsModel | None = None
    top_n: int = Field(default=5, ge=1, le=10)
    language: str = Field(default="한국어", max_length=20)


class ItineraryRequest(BaseModel):
    destination: dict
    travel_profile: dict


@router.post("/recommend")
async def travel_recommend(req: TravelRecommendRequest):
    profile = req.model_dump()
    top_n = profile.pop("top_n", 5)
    return build_recommend_response(profile, top_n=top_n)


@router.post("/itinerary")
async def travel_itinerary(req: ItineraryRequest):
    try:
        return build_itinerary_response(req.destination, req.travel_profile)
    except ItineraryUnavailable:
        raise HTTPException(
            status_code=502,
            detail="일정 생성 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요.",
        )
```

- [ ] **Step 4: server.py 배선** — In `server.py`, add the import near the other `from api.* import router` lines (after `from api.journey import router as journey_router`):

```python
from api.travel import router as travel_router
```

And add the include near the other `app.include_router(...)` calls (after `app.include_router(journey_router, prefix="/api")`):

```python
app.include_router(travel_router, prefix="/api/travel")
```

- [ ] **Step 5: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_api.py -v`
Expected (로컬): `4 skipped` (fastapi 부재). CI에서: 4 passed.

추가로 라우터 모듈이 import 가능한지(문법/순환참조 없음) 로컬에서 간접 확인:
Run: `SKIP_EXTERNAL_INIT=1 python3 -c "import ast; ast.parse(open('api/travel.py').read()); print('api/travel.py syntax OK')"`
Expected: `api/travel.py syntax OK`

- [ ] **Step 6: 커밋**

```bash
git add api/travel.py server.py tests/test_travel_api.py
git commit -m "feat(travel-api): /api/travel/recommend·itinerary 라우터 + server 배선

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 문서 동기화 + CI 등록 + 작업 로그

**Files:**
- Modify: `cowork/backend/api-reference.md`
- Modify: `.github/workflows/main-tests.yml`
- Modify: `tasklist.md`

- [ ] **Step 1: api-reference.md 동기화** — Append a new section to `cowork/backend/api-reference.md` (place after the existing Recommend/Detail section; if the file has a clear table of contents, add an entry too):

````markdown
## 여행 추천·일정 (Travel pivot, 신규)

> 기존 이민용 `/api/recommend`·`/api/detail`와 별개의 병렬 엔드포인트. 인증/결제/rate-limit 미적용(추후 별도 협의).

### POST /api/travel/recommend

규칙기반 여행지 추천 (LLM 미사용, 결정론적). `destinations.json` 기반.

Request:
```json
{
  "travel_month": 7,
  "nights": 4,
  "budget_krw": 2000000,
  "interests": ["휴양", "자연"],
  "persona": "힐링 휴양러",
  "preferred_regions": ["동남아"],
  "companions": {"type": "커플(허니문)", "headcount": 2, "ages": ["성인"], "accessibility": ["없음"], "pace": "휴양 위주"},
  "top_n": 5,
  "language": "한국어"
}
```
- `travel_month`: 1~12 또는 null, `nights`: 0~60, `top_n`: 1~10.

Response 200:
```json
{
  "top_destinations": [
    {"id": "DPS", "city": "Bali", "city_kr": "발리", "country": "Indonesia", "country_id": "ID",
     "vibe": "휴양", "budget_tier": "low", "best_months": [5,6,7,8,9], "peak_season": "...",
     "avg_flight_hours_from_icn": 7.0, "activities": ["..."], "must_see": ["..."],
     "monthly_cost_usd": 1200, "est_cost_krw": 1234000, "score": 8.4,
     "reasons": [{"point": "..."}]}
  ],
  "notes": ["...폴백 안내(있을 때)..."]
}
```

### POST /api/travel/itinerary

선택 여행지 + 여행 프로필 → Gemini가 N박M일 일정 생성 → 마크다운 + 파싱 dict 반환.

Request:
```json
{
  "destination": {"city": "Bali", "city_kr": "발리", "country_id": "ID", "vibe": "휴양",
                  "best_months": [5,6,7,8,9], "activities": ["해변","서핑"], "must_see": ["우붓"],
                  "est_cost_krw": 1500000},
  "travel_profile": {"language": "한국어", "nights": 4, "travel_month": 7,
                     "interests": ["휴양"], "persona": "힐링 휴양러",
                     "companions": {"type": "커플(허니문)", "pace": "휴양 위주"}}
}
```

Response 200:
```json
{"markdown": "# 🗺️ 발리 4박 5일 ...", "itinerary": {"city": "...", "days": [...], "...": "..."}}
```
에러: `502` — LLM 서비스 불안정.
````

- [ ] **Step 2: CI 등록** — In `.github/workflows/main-tests.yml`, find `tests/test_itinerary_parser.py \` and add after it (preserve indent + trailing ` \`):

```yaml
            tests/test_itinerary_parser.py \
            tests/test_travel_service.py \
            tests/test_travel_api.py \
```

- [ ] **Step 3: 작업 로그** — Append to the END of the `## 2026-06-13` section in `tasklist.md`:

```markdown
- Phase 4(백엔드 배선) 완료: `api/travel_service.py`(순수 도메인 로직, LLM 주입 가능) + `api/travel.py`(FastAPI 라우터) 신설, `server.py`에 `/api/travel/recommend`·`/api/travel/itinerary` 연결. 기존 이민 엔드포인트 미변경. `cowork/backend/api-reference.md` 동기화.
- 서비스 테스트 7개(로컬, 결정론적) + 라우터 테스트 4개(CI 전용, fastapi importorskip) + CI 등록. 인증/결제/rate-limit은 추후 별도 협의.
```

- [ ] **Step 4: 전체 회귀 (로컬)** — Run:
`SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_travel_service.py tests/test_travel_api.py tests/test_itinerary_prompt.py tests/test_itinerary_parser.py tests/test_travel_recommender.py tests/test_travel_budget.py tests/test_destinations.py -q`
Expected: service 7 + api 4 skipped + itinerary 30 + recommender 35 + budget 8 + destinations 22 = **102 passed, 4 skipped**.

- [ ] **Step 5: CI 등록 확인** — Run:
`grep -n "test_travel_service\|test_travel_api" .github/workflows/main-tests.yml`
Expected: 두 줄 표시.

- [ ] **Step 6: 커밋**

```bash
git add cowork/backend/api-reference.md .github/workflows/main-tests.yml tasklist.md
git commit -m "docs(travel-api): api-reference 동기화 + 테스트 CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (Phase 4 = 백엔드 배선 범위로 한정):**
- 추천엔진을 엔드포인트로 노출 → `POST /api/travel/recommend` (Task 1 service + Task 3 router) ✅
- 일정 플래너를 엔드포인트로 노출 → `POST /api/travel/itinerary` (Task 1/2 service + Task 3 router) ✅
- 기존 이민 경로 격리 → server.py는 import/​include만 추가, 신규 파일만 ✅
- 문서 동기화 규칙 → Task 4 api-reference.md ✅
- 프론트엔드 전환은 이 플랜 범위 밖(Phase 4b) — 의도적 제외 ✅

**2. Placeholder scan:** 모든 step에 실제 코드/명령/기대출력. TBD 없음. ✅

**3. Type consistency:**
- `build_recommend_response(profile, top_n=5)` / `build_itinerary_response(destination, travel_profile, llm_fn=None)` 시그니처가 Task1 정의·Task2 테스트·Task3 라우터 호출에서 일치 ✅
- 라우터는 `build_itinerary_response(req.destination, req.travel_profile)`로 호출(llm_fn 생략 → 실서비스). Task3 라우터 테스트는 `travel_mod.build_itinerary_response`를 2-인자 시그니처로 monkeypatch → 일치 ✅
- `ItineraryUnavailable`가 service 정의·router import·테스트 참조에서 동일 ✅
- `recommend_destinations(profile, top_n=...)`는 Phase 2 공개 시그니처와 일치 ✅
- 라우터 모델 `top_n` 검증(ge=1, le=10) → 테스트 `top_n=99` → 422 ✅

**4. 테스트 합계:** service = Task1(4) + Task2(3) = 7(로컬). api = 4(CI). Phase 4 신규 = 11. 로컬 회귀 102 passed + 4 skipped.

**5. 환경 주의(실행자 가이드):** 로컬에 `fastapi`/`openai` 부재. `tests/test_travel_api.py`는 `pytest.importorskip("fastapi")`로 로컬에서 skip되고 CI에서 실행된다. `api/travel_service.py`는 fastapi/openai를 모듈 레벨에서 import하지 않으며 openai는 `build_itinerary_response`의 lazy import로만 접근하므로 서비스 테스트가 로컬에서 통과한다. `server.py` 수정 후 서버를 로컬 실행해 검증할 필요는 없다(fastapi 부재) — 문법/순환참조는 Task3 Step5의 ast.parse로 확인.
