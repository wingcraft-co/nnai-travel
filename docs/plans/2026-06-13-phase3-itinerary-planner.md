# Phase 3 — LLM N박M일 일정 플래너 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택한 여행지(Phase 2 추천 카드)와 여행 프로필(기간·시기·관심사·성향·동행·페이스)을 받아, Gemini가 N박 M일 일정표(Day별 항목)를 생성하도록 하는 프롬프트와, 그 JSON 응답을 안전하게 파싱·마크다운 렌더링하는 모듈을 신설한다.

**Architecture:** 기존 이민용 Step 2 (`prompts/builder.py`의 `build_detail_prompt`, `api/parser.py`의 `format_step2_markdown`)는 **변경하지 않고**, 여행 일정 전용 병렬 모듈을 신설한다 — `prompts/itinerary.py`(순수 헬퍼 + 프롬프트 빌더), `prompts/itinerary_system.py`(시스템 프롬프트 ko/en), `api/itinerary_parser.py`(JSON 파싱 + 마크다운 렌더링). LLM 호출(`api/hf_client.py`)과 FastAPI 엔드포인트 배선은 이 Phase 범위가 아니다(Phase 4). 모든 신규 함수는 결정론적이라 네트워크 없이 테스트한다.

**Tech Stack:** Python 3, pytest. 외부 의존성 없음. 테스트는 `SKIP_EXTERNAL_INIT=1 python3 -m pytest`.

---

## 격리/원칙 (필수)

- `prompts/builder.py`, `prompts/system.py`, `api/parser.py` 등 이민 경로는 **변경 금지**. 신규 파일만 추가한다.
- push는 항상 `develop`. `main` 금지.
- 새 테스트 파일은 `.github/workflows/main-tests.yml`에 등록(Task 5).
- 작업 로그는 루트 `tasklist.md`(Task 5).
- 엔드포인트/DB/스키마 변경 없음 → `cowork/backend/*` 동기화 불필요(이 Phase 한정).

## 입력/출력 계약

`build_itinerary_prompt(destination, travel_profile) -> list[dict]`

- `destination`: Phase 2 `recommend_destinations`의 카드 dict. 사용 필드: `city`, `city_kr`, `country_id`, `vibe`, `best_months`, `activities`, `must_see`, `est_cost_krw`(선택).
- `travel_profile`: `{language, nights, travel_month, interests, persona, companions:{type,ages,pace,...}}`.
- 반환: `[{"role":"system","content":...},{"role":"user","content":...}]` (Gemini OpenAI-compat messages).

LLM이 생성할 일정 JSON 스키마(시스템 프롬프트에 명시):

```json
{
  "city": "Bali",
  "city_kr": "발리",
  "country_id": "ID",
  "trip_title": "발리 4박 5일 힐링 여행",
  "summary": "1~2문장 도입 (타로 톤)",
  "days": [
    {"day": 1, "theme": "도착 & 적응",
     "items": [
       {"time": "오전", "activity": "응우라라이 공항 도착, 숙소 체크인", "category": "이동", "tip": "택시보다 Grab이 저렴"},
       {"time": "오후", "activity": "짱구 해변 산책", "category": "관광", "tip": "선셋 시간대 추천"}
     ]}
  ],
  "packing_tips": ["가벼운 여름옷", "자외선 차단제"],
  "budget_estimate_krw": 1500000,
  "local_tips": ["현금(IDR) 일부 준비", "사원 방문 시 사롱 착용"]
}
```

`category` 허용값: `이동`, `관광`, `식사`, `숙소`, `액티비티`, `휴식` (EN: `transport`, `sightseeing`, `food`, `stay`, `activity`, `rest`).

## File Structure

- `prompts/itinerary.py` (Create) — 순수 헬퍼(`nights_to_label`, `pace_instruction`, `companion_instruction`, `interest_emphasis`, `persona_emphasis`) + `build_itinerary_prompt`. 책임: 프로필 → 프롬프트 messages.
- `prompts/itinerary_system.py` (Create) — `ITINERARY_SYSTEM_PROMPT`, `ITINERARY_SYSTEM_PROMPT_EN` 문자열 상수. 책임: 출력 규칙·스키마.
- `api/itinerary_parser.py` (Create) — `parse_itinerary(raw_text)`, `format_itinerary_markdown(data)`. 책임: LLM 응답 → dict → 마크다운.
- `tests/test_itinerary_prompt.py` (Create) — 헬퍼 + 빌더 테스트.
- `tests/test_itinerary_parser.py` (Create) — 파싱 + 렌더링 테스트.
- `.github/workflows/main-tests.yml` (Modify) — 두 테스트 등록.
- `tasklist.md` (Modify) — 2026-06-13 로그.

---

### Task 1: 프롬프트 헬퍼 (`prompts/itinerary.py` — 순수 함수)

**Files:**
- Create: `prompts/itinerary.py`
- Test: `tests/test_itinerary_prompt.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_itinerary_prompt.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompts.itinerary'`

- [ ] **Step 3: 헬퍼 구현** — Create `prompts/itinerary.py`:

> NOTE (실행자): 이 Task 1 버전의 `prompts/itinerary.py`에는 `from prompts.itinerary_system import ...` 라인을 **넣지 않는다**. `itinerary_system.py`는 Task 2에서 생성되며, 그때 import와 `build_itinerary_prompt`를 함께 추가한다. Task 1 테스트는 헬퍼 함수만 호출하므로 import 없이 통과한다.

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_prompt.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add prompts/itinerary.py tests/test_itinerary_prompt.py
git commit -m "feat(itinerary): 여행 일정 프롬프트 헬퍼 (순수 함수)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 시스템 프롬프트 + `build_itinerary_prompt`

**Files:**
- Create: `prompts/itinerary_system.py`
- Modify: `prompts/itinerary.py` (import 추가 + `build_itinerary_prompt` 추가)
- Test: `tests/test_itinerary_prompt.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가** — Append to `tests/test_itinerary_prompt.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_prompt.py -k "build" -v`
Expected: FAIL — `AttributeError: module 'prompts.itinerary' has no attribute 'build_itinerary_prompt'` (또는 ITINERARY_SYSTEM_PROMPT 미정의)

- [ ] **Step 3: 시스템 프롬프트 작성** — Create `prompts/itinerary_system.py`:

```python
"""prompts/itinerary_system.py — 여행 일정 생성 시스템 프롬프트 (ko/en)."""

ITINERARY_SYSTEM_PROMPT = """당신은 타로 리더이자 여행 일정 설계 전문가입니다.
선택된 여행지를 해석하듯 따뜻하고 설레는 톤으로 소개하되, 일정은 현실적이고 실행 가능하게 작성하세요.
summary는 "이 여행지가 당신을 기다리고 있어요" 같은 느낌으로 1~2문장 작성하세요.

선택된 여행지와 여행 프로필을 바탕으로 N박 M일 일정표를 JSON으로 작성하세요.

[출력 규칙]
1. 순수 JSON만 출력하세요. 코드 블록이나 설명 텍스트 없이.
2. 모든 텍스트 필드는 한국어로 작성하세요.
3. days 배열은 요청된 일수(M일)와 정확히 일치해야 합니다.
4. 각 day의 items는 최소 1개 이상, category는 다음 중 하나: 이동, 관광, 식사, 숙소, 액티비티, 휴식.
5. 제공된 추천 명소(must_see)와 활동(activities)을 일정에 반드시 반영하세요.
6. JSON이 잘리지 않도록 완전한 JSON을 출력하세요.

[출력 스키마 — 정확히 따를 것]
{
  "city": "도시명(영문)",
  "city_kr": "도시명(한글)",
  "country_id": "ISO-2",
  "trip_title": "여행 제목 (예: 발리 4박 5일 힐링 여행)",
  "summary": "1~2문장 도입",
  "days": [
    {
      "day": 1,
      "theme": "그날의 테마",
      "items": [
        {"time": "오전", "activity": "구체적 활동", "category": "관광", "tip": "실용 팁"}
      ]
    }
  ],
  "packing_tips": ["준비물 1", "준비물 2", "준비물 3"],
  "budget_estimate_krw": 1500000,
  "local_tips": ["현지 팁 1", "현지 팁 2", "현지 팁 3"]
}"""


ITINERARY_SYSTEM_PROMPT_EN = """You are a tarot reader and expert travel itinerary designer.
Introduce the destination in a warm, exciting tone, but keep the itinerary realistic and actionable.
Write the summary in 1-2 sentences, e.g. "This destination has been waiting for you..."

Based on the selected destination and travel profile, write an N-night itinerary in JSON.

[OUTPUT RULES]
1. Output ONLY pure JSON — no code blocks, no extra text.
2. All text fields in English.
3. The days array must match exactly the requested number of days.
4. Each day's items has at least 1 entry; category must be one of: transport, sightseeing, food, stay, activity, rest.
5. Incorporate the provided must_see spots and activities into the plan.
6. Output complete, valid JSON — do not truncate.

[OUTPUT SCHEMA]
{
  "city": "City (English)",
  "city_kr": "City (Korean)",
  "country_id": "ISO-2",
  "trip_title": "Trip title (e.g. Bali 4N5D Healing Trip)",
  "summary": "1-2 sentence intro",
  "days": [
    {"day": 1, "theme": "Day theme",
     "items": [{"time": "Morning", "activity": "Specific activity", "category": "sightseeing", "tip": "Practical tip"}]}
  ],
  "packing_tips": ["Item 1", "Item 2", "Item 3"],
  "budget_estimate_krw": 1500000,
  "local_tips": ["Local tip 1", "Local tip 2", "Local tip 3"]
}"""
```

- [ ] **Step 4: 빌더 구현** — In `prompts/itinerary.py`, ADD the import at the top (just under `from __future__ import annotations`):

```python
from prompts.itinerary_system import ITINERARY_SYSTEM_PROMPT, ITINERARY_SYSTEM_PROMPT_EN
```

Then APPEND `build_itinerary_prompt` to the END of `prompts/itinerary.py`:

```python
def build_itinerary_prompt(destination: dict, travel_profile: dict) -> list[dict]:
    """선택 여행지 + 여행 프로필 → 일정 생성 messages list."""
    language   = travel_profile.get("language", "한국어")
    nights     = int(travel_profile.get("nights") or 0)
    month      = travel_profile.get("travel_month")
    interests  = travel_profile.get("interests") or []
    persona    = travel_profile.get("persona") or ""
    companions = travel_profile.get("companions") or {}
    pace       = companions.get("pace") or ""

    city       = destination.get("city", "")
    city_kr    = destination.get("city_kr", city)
    country_id = destination.get("country_id", "")
    must_see   = destination.get("must_see") or []
    activities = destination.get("activities") or []
    est_krw    = destination.get("est_cost_krw")

    label          = nights_to_label(nights, language)
    pace_line      = pace_instruction(pace, language)
    comp_line      = companion_instruction(companions, language)
    interest_line  = interest_emphasis(interests, language)
    persona_line   = persona_emphasis(persona, language)

    # 지시 라인들(빈 문자열은 자동 제외)
    directives = [d for d in (persona_line, interest_line, comp_line, pace_line) if d]
    directive_block = ("\n".join(f"- {d}" for d in directives)) if directives else ""

    en = language == "English"
    must_see_str   = ", ".join(must_see) if must_see else ("none provided" if en else "제공된 명소 없음")
    activities_str = ", ".join(activities) if activities else ("none provided" if en else "제공된 활동 없음")
    est_str = ""
    if est_krw:
        est_str = (f"\nReference budget: about {est_krw:,} KRW per person."
                   if en else f"\n참고 예산: 1인 약 {est_krw:,}원.")

    if en:
        month_line = f"Travel month: {month}" if month else "Travel month: flexible"
        user_message = (
            f"Destination: {city} ({country_id})\n"
            f"Duration: {label}\n"
            f"{month_line}\n"
            f"Must-see spots: {must_see_str}\n"
            f"Suggested activities: {activities_str}"
            f"{est_str}\n\n"
            f"Planning directives:\n{directive_block}\n\n"
            "Write a complete day-by-day itinerary in pure JSON following the schema."
        )
        system_prompt = ITINERARY_SYSTEM_PROMPT_EN
    else:
        month_line = f"여행 시기: {month}월" if month else "여행 시기: 미정"
        user_message = (
            f"여행지: {city_kr} ({city}, {country_id})\n"
            f"여행 기간: {label}\n"
            f"{month_line}\n"
            f"대표 명소: {must_see_str}\n"
            f"추천 활동: {activities_str}"
            f"{est_str}\n\n"
            f"일정 구성 지침:\n{directive_block}\n\n"
            "위 정보를 바탕으로 Day별 상세 일정을 반드시 순수 JSON으로 작성하세요."
        )
        system_prompt = ITINERARY_SYSTEM_PROMPT

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
```

Also re-export the system prompt names so tests can read them as `I.ITINERARY_SYSTEM_PROMPT` — they are already importable because of the top-level import added above (they become module attributes of `prompts.itinerary`).

- [ ] **Step 5: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_prompt.py -v`
Expected: PASS (13 + 8 = 21 passed)

- [ ] **Step 6: 커밋**

```bash
git add prompts/itinerary_system.py prompts/itinerary.py tests/test_itinerary_prompt.py
git commit -m "feat(itinerary): 일정 시스템 프롬프트 + build_itinerary_prompt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 응답 파서 (`api/itinerary_parser.py` — `parse_itinerary`)

**Files:**
- Create: `api/itinerary_parser.py`
- Test: `tests/test_itinerary_parser.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_itinerary_parser.py`:

```python
"""tests/test_itinerary_parser.py — 일정 응답 파싱/렌더링 테스트"""
import json
from api import itinerary_parser as P


_GOOD = {
    "city": "Bali", "city_kr": "발리", "country_id": "ID",
    "trip_title": "발리 4박 5일 힐링 여행",
    "summary": "발리가 당신을 기다리고 있어요.",
    "days": [
        {"day": 1, "theme": "도착", "items": [
            {"time": "오후", "activity": "숙소 체크인", "category": "이동", "tip": "Grab 이용"}]},
        {"day": 2, "theme": "해변", "items": [
            {"time": "오전", "activity": "짱구 해변", "category": "관광", "tip": "선셋 추천"}]},
    ],
    "packing_tips": ["여름옷", "선크림"],
    "budget_estimate_krw": 1500000,
    "local_tips": ["현금 준비", "사롱 착용"],
}


# ---------- parse_itinerary ----------

def test_parse_plain_json():
    out = P.parse_itinerary(json.dumps(_GOOD, ensure_ascii=False))
    assert out["city"] == "Bali"
    assert len(out["days"]) == 2

def test_parse_code_fenced_json():
    raw = "```json\n" + json.dumps(_GOOD, ensure_ascii=False) + "\n```"
    out = P.parse_itinerary(raw)
    assert out["trip_title"] == "발리 4박 5일 힐링 여행"

def test_parse_json_with_surrounding_text():
    raw = "여기 일정입니다:\n" + json.dumps(_GOOD, ensure_ascii=False) + "\n감사합니다."
    out = P.parse_itinerary(raw)
    assert out["country_id"] == "ID"

def test_parse_failure_returns_fallback():
    out = P.parse_itinerary("완전히 깨진 응답 — JSON 없음")
    assert out["days"] == []
    assert "_raw" in out
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.itinerary_parser'`

- [ ] **Step 3: 파서 구현** — Create `api/itinerary_parser.py`:

```python
"""api/itinerary_parser.py — 여행 일정 LLM 응답 파싱 + 마크다운 렌더링.

기존 이민용 api/parser.py 와 독립적인 병렬 모듈.
"""
from __future__ import annotations

import json
import re


def _coerce(parsed: dict) -> dict:
    """필수 키 누락 시 안전 기본값으로 보정."""
    parsed.setdefault("city", "")
    parsed.setdefault("city_kr", parsed.get("city", ""))
    parsed.setdefault("country_id", "")
    parsed.setdefault("trip_title", "")
    parsed.setdefault("summary", "")
    parsed.setdefault("days", [])
    parsed.setdefault("packing_tips", [])
    parsed.setdefault("local_tips", [])
    return parsed


def parse_itinerary(raw_text: str) -> dict:
    """LLM 응답 텍스트에서 일정 JSON을 추출. 실패 시 폴백 dict 반환."""
    # 1) 코드블록 내부 JSON
    for match in re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw_text):
        try:
            return _coerce(json.loads(match.strip()))
        except json.JSONDecodeError:
            continue
    # 2) 중괄호 덩어리 (긴 것 우선)
    for match in sorted(re.findall(r"\{[\s\S]*\}", raw_text), key=len, reverse=True):
        try:
            return _coerce(json.loads(match))
        except json.JSONDecodeError:
            continue
    # 3) 폴백
    return {
        "city": "", "city_kr": "", "country_id": "", "trip_title": "",
        "summary": "일정을 불러오지 못했습니다. 다시 시도해 주세요.",
        "days": [], "packing_tips": [], "local_tips": [],
        "_raw": raw_text,
    }
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_parser.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/itinerary_parser.py tests/test_itinerary_parser.py
git commit -m "feat(itinerary): 일정 응답 파서 (robust JSON 추출 + 폴백)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 마크다운 렌더러 (`format_itinerary_markdown`)

**Files:**
- Modify: `api/itinerary_parser.py`
- Test: `tests/test_itinerary_parser.py`

- [ ] **Step 1: 실패 테스트 추가** — Append to `tests/test_itinerary_parser.py`:

```python
# ---------- format_itinerary_markdown ----------

def test_format_has_title_and_summary():
    md = P.format_itinerary_markdown(_GOOD)
    assert "발리 4박 5일 힐링 여행" in md
    assert "발리가 당신을 기다리고 있어요." in md

def test_format_renders_each_day():
    md = P.format_itinerary_markdown(_GOOD)
    assert "Day 1" in md and "Day 2" in md
    assert "짱구 해변" in md

def test_format_renders_item_category_and_tip():
    md = P.format_itinerary_markdown(_GOOD)
    assert "관광" in md       # category 라벨
    assert "선셋 추천" in md   # tip

def test_format_renders_budget_krw():
    md = P.format_itinerary_markdown(_GOOD)
    assert "1,500,000" in md

def test_format_renders_packing_and_local_tips():
    md = P.format_itinerary_markdown(_GOOD)
    assert "여름옷" in md
    assert "사롱 착용" in md

def test_format_empty_days_is_graceful():
    md = P.format_itinerary_markdown({"trip_title": "", "days": []})
    assert isinstance(md, str)  # 크래시 없음

def test_format_english_labels():
    data = dict(_GOOD)
    data["_language"] = "English"
    md = P.format_itinerary_markdown(data)
    assert "Day 1" in md
    assert "Packing" in md or "Budget" in md
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_parser.py -k "format" -v`
Expected: FAIL — `AttributeError: module 'api.itinerary_parser' has no attribute 'format_itinerary_markdown'`

- [ ] **Step 3: 렌더러 구현** — Append to `api/itinerary_parser.py`:

```python
def _fmt_krw(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def format_itinerary_markdown(data: dict) -> str:
    """파싱된 일정 dict → 마크다운 문자열. 누락 필드는 우아하게 생략."""
    if not data:
        return "일정을 불러오지 못했습니다."

    is_en = data.get("_language") == "English"
    lines: list[str] = []

    title = data.get("trip_title") or data.get("city_kr") or data.get("city") or (
        "Travel Itinerary" if is_en else "여행 일정")
    lines.append(f"# 🗺️ {title}\n")

    summary = data.get("summary")
    if summary:
        lines.append(f"> {summary}\n")

    for day in data.get("days", []):
        day_num = day.get("day", "")
        theme = day.get("theme", "")
        header = f"## Day {day_num}"
        if theme:
            header += f" — {theme}"
        lines.append(header)
        for item in day.get("items", []):
            time = item.get("time", "")
            activity = item.get("activity", "")
            category = item.get("category", "")
            tip = item.get("tip", "")
            cat = f" `{category}`" if category else ""
            head = f"- **{time}**{cat} {activity}".rstrip()
            lines.append(head)
            if tip:
                lines.append(f"  - 💡 {tip}")
        lines.append("")

    budget = data.get("budget_estimate_krw")
    if budget:
        label = "Estimated Budget" if is_en else "예상 경비"
        unit = "KRW per person" if is_en else "원 (1인 기준)"
        lines.append(f"## 💰 {label}\n")
        lines.append(f"- {_fmt_krw(budget)} {unit}\n")

    packing = data.get("packing_tips") or []
    if packing:
        lines.append(f"## 🎒 {'Packing Tips' if is_en else '준비물'}\n")
        for p in packing:
            lines.append(f"- {p}")
        lines.append("")

    local = data.get("local_tips") or []
    if local:
        lines.append(f"## 📌 {'Local Tips' if is_en else '현지 팁'}\n")
        for t in local:
            lines.append(f"- {t}")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: 전체 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_parser.py tests/test_itinerary_prompt.py -v`
Expected: PASS (parser 4 + 7 = 11, prompt 21 = 총 32 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/itinerary_parser.py tests/test_itinerary_parser.py
git commit -m "feat(itinerary): 일정 마크다운 렌더러 (Day별/예산/팁)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: CI 등록 + 작업 로그

**Files:**
- Modify: `.github/workflows/main-tests.yml`
- Modify: `tasklist.md`

- [ ] **Step 1: CI 등록** — In `.github/workflows/main-tests.yml`, find the line `tests/test_travel_recommender.py \` and add the two new files immediately after it (preserve indentation + trailing ` \`):

```yaml
            tests/test_travel_recommender.py \
            tests/test_itinerary_prompt.py \
            tests/test_itinerary_parser.py \
```

- [ ] **Step 2: 작업 로그** — In `tasklist.md`, append to the END of the `## 2026-06-13` section:

```markdown
- Phase 3 완료: 여행 일정(N박M일) LLM 플래너 신설 — `prompts/itinerary.py`(프로필→프롬프트 헬퍼+빌더), `prompts/itinerary_system.py`(ko/en 스키마), `api/itinerary_parser.py`(robust 파싱 + Day별 마크다운 렌더). 기존 이민용 builder.py·parser.py 미변경.
- 일정 플래너 테스트 32개(프롬프트 21 + 파서/렌더 11) 통과 + CI 등록. LLM 호출/엔드포인트 배선은 Phase 4 범위.
```

- [ ] **Step 3: 전체 회귀** — Run:
`SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_itinerary_prompt.py tests/test_itinerary_parser.py -q`
Expected: 32 passed.

- [ ] **Step 4: CI 등록 확인** — Run:
`grep -n "test_itinerary" .github/workflows/main-tests.yml`
Expected: 두 줄이 올바른 위치에 표시됨.

- [ ] **Step 5: 커밋**

```bash
git add .github/workflows/main-tests.yml tasklist.md
git commit -m "chore: 일정 플래너 테스트 CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage:**
- spec "Phase 3 LLM 플래너: Step 2 N박M일 일정 가이드 프롬프트" → Task 1(헬퍼) + Task 2(시스템 프롬프트 + 빌더). N박M일 라벨·일수 일치 규칙 명시 ✅
- spec 동행/페이스/관심사/성향 반영 → `companion_instruction`/`pace_instruction`/`interest_emphasis`/`persona_emphasis`가 directive 블록으로 주입 ✅
- spec 추천 보고서 기반 일정 → `destination`의 must_see/activities를 프롬프트에 주입, 일정에 반영하도록 지시 ✅
- spec "DB 불필요" → 전부 순수 함수/문자열, 네트워크 없음 ✅
- spec 격리 → 신규 파일만, 이민 경로 미변경 ✅
- 결정론적 테스트 → LLM 호출 제외, 프롬프트 조립/파싱/렌더만 검증 ✅
- 파싱 견고성(코드펜스/혼합텍스트/폴백) → Task 3 ✅; 렌더 누락필드 우아 처리 → Task 4 ✅

**2. Placeholder scan:** 모든 step에 실제 코드/명령/기대출력. TBD/TODO 없음. ✅ (단, Task 1의 import 생략 주의사항을 NOTE로 명시 — Task 2에서 import 추가.)

**3. Type consistency:**
- `nights_to_label(nights, language="한국어")` 시그니처가 Task1 정의·Task2 호출에서 동일 ✅
- `pace_instruction`/`companion_instruction`/`interest_emphasis`/`persona_emphasis` 시그니처 일관, build에서 동일 인자로 호출 ✅
- `parse_itinerary`(Task3) 반환 dict 키(city/city_kr/country_id/trip_title/summary/days/packing_tips/local_tips)와 `format_itinerary_markdown`(Task4)이 읽는 키 일치. budget_estimate_krw는 parse에서 보정 대상 아니지만 format에서 `.get`으로 안전 접근 ✅
- format의 언어 분기는 `data["_language"]` 기준 — 테스트와 일치. (호출부가 파싱 결과에 `_language`를 주입하는 방식; Phase 4 배선 시 설정. parse 단계에서는 주입하지 않음 — 의도된 것.) ✅
- 시스템 프롬프트 상수명(ITINERARY_SYSTEM_PROMPT/_EN)이 itinerary_system.py 정의·itinerary.py import·테스트 참조에서 동일 ✅

**4. 테스트 합계:** 프롬프트 = Task1(13) + Task2(8) = 21. 파서/렌더 = Task3(4) + Task4(7) = 11. Phase 3 합 **32**. 실행 시 실제 수집 개수 기준으로 판단, 불일치 시 누락 의심.

**5. 주의(실행자 가이드):** Task 1에서 `prompts/itinerary.py` 최상단 import(`from prompts.itinerary_system import ...`)를 **넣지 않는다** — Task 2에서 itinerary_system.py 생성과 함께 추가. Task 1 테스트는 헬퍼만 호출하므로 import 없이 통과한다.
