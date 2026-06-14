# Phase 7 — 프론트엔드 여행 입력 + 추천 흐름 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 온보딩 입력폼·recommend BFF·타로 결과 화면을 이민 → 휴가 여행지 추천으로 전환하고, `/api/travel/recommend`에 연결한다.

**Architecture:** 5스텝 입력폼 구조·`SelectCard`·draft 자동저장·타로 카드 UX는 유지하고 **데이터/카피만 여행으로 교체**. recommend BFF는 `/api/travel/recommend`를 호출하고 응답을 `destinations.json`으로 보강. 카드 세션/`reveal`(2단계 세션)은 여행 백엔드에 없으므로 제거 — `top_destinations`를 직접 카드로 표시하고 flip 애니메이션만 클라이언트에서 수행.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind 4, framer-motion, next-intl. 순수 로직 테스트는 `node --test --experimental-strip-types <file>.test.mjs`.

> **사전 필독:** `frontend/AGENTS.md` — Next.js 16은 훈련 데이터와 다를 수 있으니 코드 작성 전 `frontend/node_modules/next/dist/docs/` 확인. 디자인은 `docs/designs/tarot-card-design.md` 준수(타로 카드 변경 시).

---

## 격리/원칙 (필수)

- 백엔드 API 스키마 변경 금지(여행 API는 확정됨). 계약은 `cowork/backend/api-reference.md`(§여행 추천·일정 API).
- 디자인 시스템 tweakcn Amber Mono 2.0 — CSS 변수만, HEX 금지.
- push는 항상 `develop`. `main` 금지.
- 새 `*.test.mjs`는 `.github/workflows/main-tests.yml`의 "Frontend regression tests" 줄(line 96)에 추가(Task 6).
- 작업 로그 → 루트 `tasklist.md`(Task 6).
- 모든 명령은 리포 루트(`/Users/yoroji/Documents/hackathon/nnai-travel`)에서 실행. `frontend/` 경로를 명시.

## 여행 추천 계약 (참조)

`POST /api/travel/recommend` request:
```json
{"travel_month": 7, "nights": 4, "budget_krw": 2000000, "interests": ["휴양","자연"],
 "persona": "힐링 휴양러", "preferred_regions": ["동남아"],
 "companions": {"type": "커플(허니문)", "headcount": 2, "ages": ["성인"], "accessibility": ["없음"], "pace": "휴양 위주"},
 "top_n": 5, "language": "한국어"}
```
response: `{"top_destinations": [{id, city, city_kr, country, country_id, vibe, budget_tier, best_months, peak_season, avg_flight_hours_from_icn, activities, must_see, monthly_cost_usd, est_cost_krw, score, reasons:[{point}]}], "notes": [...]}`

## File Structure

- `frontend/src/lib/destination-enrich.ts` (Create) — 순수 함수 `enrichDestinations(list, descriptions)`: `top_destinations`에 `city_description` 보강. DOM/네트워크 비의존.
- `frontend/src/lib/travel-recommend-request.ts` (Create) — 순수 함수 `buildTravelRecommendRequest(form, locale)`: 폼 상태 → `/api/travel/recommend` request body 매핑 + `clampMonth`/`clampNights` 등 검증.
- `frontend/src/lib/destination-enrich.test.mjs` (Create) — enrich 테스트.
- `frontend/src/lib/travel-recommend-request.test.mjs` (Create) — request 매핑 테스트.
- `frontend/src/app/api/recommend/route.ts` (Modify) — `/api/travel/recommend` 호출 + `enrichDestinations`. 이민 enrichment 제거.
- `frontend/src/app/api/reveal/route.ts` (Delete) — 여행 흐름에서 미사용.
- `frontend/src/app/[locale]/onboarding/form/page.tsx` (Modify) — `FormData` 여행 필드 교체, 5스텝 옵션/카피 교체, 완료 시 `buildTravelRecommendRequest` 결과를 `RECOMMEND_PAYLOAD_KEY`로 저장.
- `frontend/src/app/[locale]/result/page.tsx` (Modify) — `top_destinations` 직접 소비, `reveal` 호출/세션 단계 제거, 카드 flip은 클라이언트.
- `frontend/src/components/tarot/{TarotCard,TarotDeck,CityCompare,TarotReading}.tsx` (Modify) — 여행지 필드(vibe/best_months/est_cost_krw/activities/must_see) 표시.
- `frontend/src/messages/ko.json`, `frontend/src/messages/en.json` (Modify) — 여행 카피.
- `.github/workflows/main-tests.yml`, `tasklist.md` (Modify, Task 6).

---

### Task 1: destination enrichment 순수 헬퍼

**Files:**
- Create: `frontend/src/lib/destination-enrich.ts`
- Test: `frontend/src/lib/destination-enrich.test.mjs`

- [ ] **Step 1: 실패 테스트 작성** — Create `frontend/src/lib/destination-enrich.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { enrichDestinations } from "./destination-enrich.ts";

test("passes through destination fields unchanged", () => {
  const list = [{ id: "DPS", city: "Bali", country_id: "ID", vibe: "휴양" }];
  const out = enrichDestinations(list, {});
  assert.equal(out[0].id, "DPS");
  assert.equal(out[0].city, "Bali");
  assert.equal(out[0].vibe, "휴양");
});

test("adds city_description from descriptions map by ID_SLUG key", () => {
  const list = [{ id: "DPS", city: "Bali", country_id: "ID" }];
  const descriptions = { ID_BALI: "발리 설명" };
  const out = enrichDestinations(list, descriptions);
  assert.equal(out[0].city_description, "발리 설명");
});

test("city_description is null when no match", () => {
  const out = enrichDestinations([{ id: "X", city: "Nowhere", country_id: "ZZ" }], {});
  assert.equal(out[0].city_description, null);
});

test("returns empty array for empty input", () => {
  assert.deepEqual(enrichDestinations([], {}), []);
  assert.deepEqual(enrichDestinations(undefined, {}), []);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test --experimental-strip-types frontend/src/lib/destination-enrich.test.mjs`
Expected: FAIL — cannot find module `./destination-enrich.ts`.

- [ ] **Step 3: 구현** — Create `frontend/src/lib/destination-enrich.ts`:

```typescript
type Destination = Record<string, unknown> & { city?: string; country_id?: string };

/** city 이름 → CITY_SLUG (대문자, 공백→_, 괄호 제거). recommend BFF의 기존 규칙과 동일. */
function citySlug(city: string): string {
  return city.toUpperCase().replace(/ /g, "_").replace(/[()]/g, "");
}

/**
 * 여행 추천 top_destinations에 city_description을 보강한다.
 * 백엔드가 이미 여행 필드(vibe/best_months/activities 등)를 채워 반환하므로 통과시키고,
 * 카드 본문용 설명만 destinations 설명 맵에서 ID_SLUG 키로 조회해 붙인다.
 */
export function enrichDestinations(
  list: Destination[] | undefined,
  descriptions: Record<string, string>
): Destination[] {
  if (!list) return [];
  return list.map((d) => {
    const city = (d.city as string) ?? "";
    const countryId = (d.country_id as string) ?? "";
    const key = `${countryId}_${citySlug(city)}`;
    return { ...d, city_description: descriptions[key] ?? null };
  });
}
```

- [ ] **Step 4: 통과 확인**

Run: `node --test --experimental-strip-types frontend/src/lib/destination-enrich.test.mjs`
Expected: PASS (4 tests).

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/destination-enrich.ts frontend/src/lib/destination-enrich.test.mjs
git commit -m "feat(travel-fe): destination enrichment 순수 헬퍼

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 폼 → 여행 추천 request 매핑 헬퍼

**Files:**
- Create: `frontend/src/lib/travel-recommend-request.ts`
- Test: `frontend/src/lib/travel-recommend-request.test.mjs`

폼 상태(여행 입력)를 `/api/travel/recommend` request로 변환. Task 4의 `FormData` 필드와 정합.

- [ ] **Step 1: 실패 테스트 작성** — Create `frontend/src/lib/travel-recommend-request.test.mjs`:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildTravelRecommendRequest } from "./travel-recommend-request.ts";

const baseForm = {
  travel_month: 7,
  nights: 4,
  budget_krw: 2000000,
  interests: ["휴양", "자연"],
  persona: "힐링 휴양러",
  preferred_regions: ["동남아"],
  companion_type: "커플(허니문)",
  headcount: 2,
  companion_ages: ["성인"],
  accessibility: ["없음"],
  pace: "휴양 위주",
};

test("maps form to travel recommend request", () => {
  const req = buildTravelRecommendRequest(baseForm, "ko");
  assert.equal(req.travel_month, 7);
  assert.equal(req.nights, 4);
  assert.equal(req.budget_krw, 2000000);
  assert.deepEqual(req.interests, ["휴양", "자연"]);
  assert.equal(req.persona, "힐링 휴양러");
  assert.deepEqual(req.preferred_regions, ["동남아"]);
  assert.equal(req.top_n, 5);
  assert.equal(req.language, "한국어");
});

test("nests companions object", () => {
  const req = buildTravelRecommendRequest(baseForm, "ko");
  assert.equal(req.companions.type, "커플(허니문)");
  assert.equal(req.companions.headcount, 2);
  assert.deepEqual(req.companions.ages, ["성인"]);
  assert.deepEqual(req.companions.accessibility, ["없음"]);
  assert.equal(req.companions.pace, "휴양 위주");
});

test("language follows locale", () => {
  assert.equal(buildTravelRecommendRequest(baseForm, "en").language, "English");
});

test("clamps month to 1..12 or null", () => {
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: 0 }, "ko").travel_month, null);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: 13 }, "ko").travel_month, null);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, travel_month: "" }, "ko").travel_month, null);
});

test("clamps nights to 0..60", () => {
  assert.equal(buildTravelRecommendRequest({ ...baseForm, nights: 999 }, "ko").nights, 60);
  assert.equal(buildTravelRecommendRequest({ ...baseForm, nights: -1 }, "ko").nights, 0);
});

test("defaults empty arrays when missing", () => {
  const req = buildTravelRecommendRequest({}, "ko");
  assert.deepEqual(req.interests, []);
  assert.deepEqual(req.preferred_regions, []);
  assert.equal(req.companions.headcount, 1);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test --experimental-strip-types frontend/src/lib/travel-recommend-request.test.mjs`
Expected: FAIL — module not found.

- [ ] **Step 3: 구현** — Create `frontend/src/lib/travel-recommend-request.ts`:

```typescript
export interface TravelFormState {
  travel_month?: number | string;
  nights?: number | string;
  budget_krw?: number | null;
  interests?: string[];
  persona?: string;
  preferred_regions?: string[];
  companion_type?: string;
  headcount?: number;
  companion_ages?: string[];
  accessibility?: string[];
  pace?: string;
}

export interface TravelRecommendRequest {
  travel_month: number | null;
  nights: number;
  budget_krw: number | null;
  interests: string[];
  persona: string;
  preferred_regions: string[];
  companions: {
    type: string;
    headcount: number;
    ages: string[];
    accessibility: string[];
    pace: string;
  };
  top_n: number;
  language: string;
}

function clampMonth(m: unknown): number | null {
  const n = Number(m);
  if (!Number.isInteger(n) || n < 1 || n > 12) return null;
  return n;
}

function clampNights(v: unknown): number {
  const n = Number(v);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.min(60, Math.trunc(n)));
}

/** 폼 상태 → /api/travel/recommend request body. locale로 응답 언어 결정. */
export function buildTravelRecommendRequest(
  form: TravelFormState,
  locale: string
): TravelRecommendRequest {
  return {
    travel_month: clampMonth(form.travel_month),
    nights: clampNights(form.nights),
    budget_krw: form.budget_krw ?? null,
    interests: form.interests ?? [],
    persona: form.persona ?? "",
    preferred_regions: form.preferred_regions ?? [],
    companions: {
      type: form.companion_type ?? "혼자 (솔로)",
      headcount: form.headcount ?? 1,
      ages: form.companion_ages ?? [],
      accessibility: form.accessibility ?? [],
      pace: form.pace ?? "",
    },
    top_n: 5,
    language: locale === "en" ? "English" : "한국어",
  };
}
```

- [ ] **Step 4: 통과 확인**

Run: `node --test --experimental-strip-types frontend/src/lib/travel-recommend-request.test.mjs`
Expected: PASS (6 tests).

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/travel-recommend-request.ts frontend/src/lib/travel-recommend-request.test.mjs
git commit -m "feat(travel-fe): 폼→여행 추천 request 매핑 헬퍼

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: recommend BFF를 여행 엔드포인트로 전환

**Files:**
- Modify: `frontend/src/app/api/recommend/route.ts`
- Delete: `frontend/src/app/api/reveal/route.ts`

- [ ] **Step 1: recommend route 교체** — Replace the ENTIRE contents of `frontend/src/app/api/recommend/route.ts` with:

```typescript
import { NextRequest, NextResponse } from "next/server";
import cityDescriptions from "@/data/city_descriptions.json";
import { enrichDestinations } from "@/lib/destination-enrich";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const cookie = req.headers.get("cookie") ?? "";

  const apiBase = process.env.NEXT_PUBLIC_API_URL || "https://api.nnai.app";
  const response = await fetch(`${apiBase}/api/travel/recommend`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(cookie ? { Cookie: cookie } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    return NextResponse.json(
      { error: "여행 추천 API 호출 실패" },
      { status: response.status }
    );
  }

  const data = await response.json();
  data.top_destinations = enrichDestinations(
    data.top_destinations,
    cityDescriptions as Record<string, string>
  );
  return NextResponse.json(data);
}
```

> NOTE: 여행 추천은 `top_destinations`를 직접 반환 — 카드 세션/`session_id`/`parsed.top_cities` 없음. enrichment는 `city_description`만(여행 필드는 백엔드가 채움).

- [ ] **Step 2: reveal route 삭제**

Run: `git rm frontend/src/app/api/reveal/route.ts`

> 여행 흐름엔 reveal 세션 단계가 없다(Task 5에서 result 페이지의 reveal 호출 제거와 짝).

- [ ] **Step 3: 빌드 확인** — recommend route가 enrich 헬퍼를 정상 import하는지 타입 체크:

Run: `cd frontend && npx tsc --noEmit -p tsconfig.json 2>&1 | grep -E "recommend/route|destination-enrich" || echo "no type errors in changed files"`
Expected: `no type errors in changed files` (result/page는 Task 5 전까지 reveal 참조로 에러가 있을 수 있으니 변경 파일만 grep).

- [ ] **Step 4: 커밋**

```bash
git add -A frontend/src/app/api/recommend/route.ts frontend/src/app/api/reveal/route.ts
git commit -m "feat(travel-fe): recommend BFF를 /api/travel/recommend로 전환 + reveal 제거

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 온보딩 입력폼 여행 전환

**Files:**
- Modify: `frontend/src/app/[locale]/onboarding/form/page.tsx`

> 654줄 대형 파일. 5스텝 구조/`SelectCard`/`ProgressBar`/draft 자동저장/persona 로딩은 **유지**하고 필드·옵션·카피만 교체한다. 작업 전 파일 전체를 Read한 뒤 아래 변경을 순서대로 적용.

- [ ] **Step 1: `FormData` 타입과 `INITIAL_FORM` 교체** — `interface FormData { ... }`와 `const INITIAL_FORM` 를 여행 스키마로 교체:

```typescript
interface FormData {
  travel_month: number | string;   // 1..12, "" = 미정
  nights: number | string;          // 박 수
  budget_krw: number | null;        // 총 예산(원)
  interests: string[];              // 휴양·자연·도시·미식·액티비티·문화 등
  persona: string;                  // 퀴즈 결과 매핑 (힐링 휴양러 등)
  preferred_regions: string[];      // 동남아·유럽·동북아 등
  companion_type: string;           // 혼자/커플/가족/친구
  headcount: number;
  companion_ages: string[];         // 성인·아동·영유아·시니어
  accessibility: string[];          // 없음·유아동반·휠체어 등
  pace: string;                     // 휴양 위주·균형·빡빡하게
}

const INITIAL_FORM: FormData = {
  travel_month: "",
  nights: 4,
  budget_krw: null,
  interests: [],
  persona: "",
  preferred_regions: [],
  companion_type: "",
  headcount: 1,
  companion_ages: [],
  accessibility: [],
  pace: "",
};
```

- [ ] **Step 2: 헬퍼/조건 로직 교체** — `hasChildren`/`hasSpouse`(이민용)를 여행 동행 로직으로 교체:

```typescript
function hasKids(companionType: string) {
  return companionType.includes("가족") || companionType.includes("아이");
}
```

기존 `hasChildren(form.travel_type)`/`hasSpouse(...)` 사용처를 `hasKids(form.companion_type)` 기반으로 갱신(자녀 연령 스텝 노출 조건). 배우자 소득 관련 스텝/필드는 제거.

- [ ] **Step 3: 5스텝 내용 교체** — 각 스텝 JSX의 `SelectCard` 옵션과 제목/설명을 여행으로 교체. 권장 매핑:
  1. **여행 시기·기간:** `travel_month`(1~12 월 선택), `nights`(2박3일/3박4일/4박5일/일주일+).
  2. **예산:** `budget_krw`(100만 이하/100~200/200~400/400만+ → 대표값 원으로 저장).
  3. **관심사:** `interests`(휴양·자연·도시·미식·액티비티·문화·쇼핑·나이트라이프) 다중선택.
  4. **선호 권역:** `preferred_regions`(동남아·동북아·유럽·북미·오세아니아·중동·상관없음) 다중선택.
  5. **동행:** `companion_type`(혼자/커플/가족/친구) + `headcount` + 조건부 `companion_ages`/`accessibility` + `pace`.
  옵션 라벨/카피는 `getOnboardingCopy(locale)`(Task 7에서 i18n) 또는 인라인 한/영 분기. 기존 `SelectCard`/다중선택 토글 패턴 그대로 재사용.

- [ ] **Step 4: persona 매핑** — 기존 `persona_type`/`personaVector` 로딩 유지. 퀴즈 결과 persona를 여행 `form.persona`로 매핑(예: localStorage `persona_type` → 라벨). 매핑 표는 인라인 상수로:

```typescript
const PERSONA_TO_TRAVEL: Record<string, string> = {
  wanderer: "탐험가형",
  local: "현지 몰입형",
  planner: "계획형 여행자",
  free_spirit: "자유로운 영혼",
  pioneer: "오프비트 개척자",
};
```

- [ ] **Step 5: 제출 핸들러 교체** — 폼 완료 시 `buildTravelRecommendRequest`로 변환해 `RECOMMEND_PAYLOAD_KEY`에 저장 후 `/result`로 이동:

```typescript
import { buildTravelRecommendRequest } from "@/lib/travel-recommend-request";
// ...제출부:
const payload = buildTravelRecommendRequest(
  {
    travel_month: form.travel_month,
    nights: form.nights,
    budget_krw: form.budget_krw,
    interests: form.interests,
    persona: form.persona || PERSONA_TO_TRAVEL[personaType ?? ""] || "",
    preferred_regions: form.preferred_regions,
    companion_type: form.companion_type,
    headcount: form.headcount,
    companion_ages: form.companion_ages,
    accessibility: form.accessibility,
    pace: form.pace,
  },
  locale
);
localStorage.setItem("recommend_payload", JSON.stringify(payload));
router.push("/result");
```

> `RECOMMEND_PAYLOAD_KEY`는 result 페이지(`recommend_payload`)와 동일 문자열이어야 한다.

- [ ] **Step 6: draft 검증** — draft 자동저장은 `form: object`를 저장하므로 구조 변경 불필요. 단 기존 draft가 이민 스키마면 무시되도록 키 버전 올림: `frontend/src/lib/onboarding-form-draft.ts`의 `ONBOARDING_FORM_DRAFT_KEY`를 `"onboarding_form_draft_v2"`로 변경.

- [ ] **Step 7: 빌드 확인**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: 빌드 성공(form/page·result/page 타입 에러 없음 — result는 Task 5에서 함께 맞춤. 이 task만 단독 빌드 시 result 에러가 있으면 Task 5와 묶어 진행).

- [ ] **Step 8: 커밋**

```bash
git add frontend/src/app/\[locale\]/onboarding/form/page.tsx frontend/src/lib/onboarding-form-draft.ts
git commit -m "feat(travel-fe): 온보딩 입력폼 여행 스키마로 전환

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 타로 결과 화면 여행 전환 (reveal 제거)

**Files:**
- Modify: `frontend/src/app/[locale]/result/page.tsx`
- Modify: `frontend/src/components/tarot/{TarotCard,TarotDeck,CityCompare,TarotReading}.tsx`

> 결과 흐름을 `recommend → reveal → reading → done`(세션 2단계)에서 `recommend → (카드 flip) → pick → done`(단일 단계)로 단순화. 작업 전 result/page.tsx + tarot 컴포넌트를 Read.

- [ ] **Step 1: recommend 응답 소비 변경** — `result/page.tsx`의 recommend fetch 핸들러에서 `data.parsed?.top_cities`/`session_id` 대신 `data.top_destinations`를 사용. 상태 `revealedCities`/`sessionId`/`selectedIndices` 중 reveal 세션 전용 상태 제거, `allDestinations: DestinationData[]`로 통합. `clearOnboardingFormDraft(localStorage)`는 유지.

```typescript
const res = await fetch("/api/recommend", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: payloadStr, // localStorage RECOMMEND_PAYLOAD_KEY 값
});
if (!res.ok) throw new Error(`recommend error: ${res.status}`);
const data = (await res.json()) as { top_destinations: DestinationData[]; notes?: string[] };
setAllDestinations(data.top_destinations ?? []);
```

- [ ] **Step 2: reveal 호출/단계 제거** — `/api/reveal` fetch와 `selected_indices` 전송 로직, `"revealing"`/`"reading"` 스테이지 분기를 삭제. 카드 뒤집기(flip)는 클라이언트 상태(`flippedIndices`)로만 처리. 카드 선택의 종착점은 "이 여행지로 일정 만들기"(Phase 8 진입) 버튼 — Phase 8 전까지는 선택 destination을 sessionStorage(`selected_destination`)에 저장하고 비활성/placeholder 버튼으로 둔다.

- [ ] **Step 3: 세션 저장 키 정리** — `SESSION_V2_KEY`/`TAROT_SESSION_KEY` 복원 로직에서 `revealedCities`/`session_id` 의존 제거, `allDestinations` 기준으로 저장/복원. 레거시 이민 세션 키는 무시(존재 시 제거).

- [ ] **Step 4: 카드 컴포넌트 필드 교체** — `TarotCard`/`TarotDeck`/`CityCompare`/`TarotReading`에서 이민 필드(visa_type/monthly_cost_usd/nomad_score/safety_score 등) 표시를 여행 필드로 교체:
  - 카드 앞면: `city_kr`/`country`, `vibe`(분위기 태그), `est_cost_krw`(예상 경비), `best_months`(추천 시기), `score`.
  - 상세/비교: `activities`/`must_see`(가볼 곳), `avg_flight_hours_from_icn`(비행 시간), `peak_season`, `reasons[].point`.
  - 국기는 기존 `@/lib/country-flag`(country_id) 재사용.
  - 디자인 토큰/레이아웃은 `docs/designs/tarot-card-design.md` 준수, CSS 변수만.

- [ ] **Step 5: 타입 정의** — `DestinationData` 타입을 `result/page.tsx` 또는 공용 `@/lib/types`에 정의(여행 추천 응답 필드 + `city_description`). 카드 컴포넌트 props를 `CityData` → `DestinationData`로 교체.

- [ ] **Step 6: 빌드 + 수동 확인**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: 빌드 성공.
수동: `cd frontend && npm run dev` 후 `/ko/onboarding/form` 완주 → `/ko/result`에서 여행지 카드 5장 표시·flip 동작 확인(백엔드 `NEXT_PUBLIC_API_URL` 필요; 로컬 백엔드 부재 시 BFF 502는 예상).

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/app/\[locale\]/result/page.tsx frontend/src/components/tarot/
git commit -m "feat(travel-fe): 타로 결과를 여행지 추천으로 전환 (reveal 세션 제거)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: i18n 카피 + CI 등록 + 작업 로그

**Files:**
- Modify: `frontend/src/messages/ko.json`, `frontend/src/messages/en.json`
- Modify: `.github/workflows/main-tests.yml`, `tasklist.md`

- [ ] **Step 1: i18n 카피** — `ko.json`/`en.json`에 여행 입력폼·결과 화면 카피 키 추가(이민 카피 키는 미사용분 제거 또는 유지). 폼 스텝 제목/옵션 라벨, 결과 헤딩("당신을 위한 여행지 TOP 5" 등), 카드 라벨(분위기/예상경비/추천시기/가볼곳)을 ko/en 동기화. 기존 `getOnboardingCopy`/next-intl 패턴 따름.

- [ ] **Step 2: CI 등록** — `.github/workflows/main-tests.yml`의 "Frontend regression tests" `node --test ...` 줄(line 96) 끝에 추가:
```
frontend/src/lib/destination-enrich.test.mjs frontend/src/lib/travel-recommend-request.test.mjs
```

- [ ] **Step 3: 전체 프론트 테스트 (로컬)**

Run: `node --test --experimental-strip-types frontend/src/lib/destination-enrich.test.mjs frontend/src/lib/travel-recommend-request.test.mjs`
Expected: PASS (4 + 6 = 10 tests).

- [ ] **Step 4: CI 등록 확인**

Run: `grep -c "destination-enrich.test.mjs\|travel-recommend-request.test.mjs" .github/workflows/main-tests.yml`
Expected: `1` (둘 다 같은 줄).

- [ ] **Step 5: 작업 로그** — Append to the `## 2026-06-14` section in `tasklist.md`:
```markdown
- Phase 7(프론트 여행 전환·입력+추천) 완료: 온보딩 입력폼을 여행 스키마(시기·박수·예산·관심사·권역·동행)로 전환, recommend BFF를 `/api/travel/recommend`로 연결(+destinations 설명 보강, reveal 세션 제거), 타로 결과를 여행지 TOP 5 카드로 전환. `destination-enrich`·`travel-recommend-request` 순수 헬퍼 + 테스트 10개 + CI 등록.
```

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/messages/ko.json frontend/src/messages/en.json .github/workflows/main-tests.yml tasklist.md
git commit -m "docs(travel-fe): i18n 여행 카피 + CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (로드맵 Phase 7 = 입력+추천 흐름):**
- 입력폼 여행 전환(시기·박수·예산·관심사·권역·동행) → Task 4 ✅
- recommend BFF → `/api/travel/recommend` + destinations 보강 → Task 1, 3 ✅
- reveal 세션 제거(여행 백엔드에 없음) → Task 3(BFF 삭제), Task 5(페이지 호출 제거) ✅
- 타로 결과 여행지 표시 → Task 5 ✅
- i18n ko/en → Task 6 ✅
- 순수 로직 테스트 + CI 등록 → Task 1, 2, 6 ✅

**2. Placeholder scan:** 순수 헬퍼(Task 1·2)는 완전한 코드+테스트. UI task(4·5)는 대형 파일 in-place 편집이라 정확한 필드 매핑·키 문자열·조건을 명시(전체 재작성 코드 대신 수술적 지시) — 기존 패턴 재사용 전제. i18n(Task 6)은 키 추가 지시. TBD 없음. ✅

**3. Type consistency:**
- `buildTravelRecommendRequest(form, locale)` — Task 2 정의·테스트·Task 4 제출부 호출 일치 ✅
- `enrichDestinations(list, descriptions)` — Task 1 정의·테스트·Task 3 BFF 호출 일치 ✅
- `RECOMMEND_PAYLOAD_KEY = "recommend_payload"` — form 제출(Task 4 Step 5)·result 소비(Task 5 Step 1) 동일 문자열 ✅
- 응답 필드: BFF가 `top_destinations` 반환(Task 3) → result가 `data.top_destinations` 소비(Task 5) 일치. `session_id`/`top_cities` 잔존 참조는 Task 5에서 제거 ✅
- 카드 props: `CityData` → `DestinationData`(Task 5 Step 5)로 컴포넌트 일괄 교체 ✅

**4. 테스트 합계:** destination-enrich 4 + travel-recommend-request 6 = 10(로컬+CI). UI는 빌드 + 수동 확인.

**5. 환경 주의(실행자 가이드):** Next.js 16 — 코드 전 `frontend/node_modules/next/dist/docs/` 확인(`frontend/AGENTS.md`). 로컬 백엔드 부재 시 `/api/travel/recommend` BFF는 502 가능 — UI 동작은 빌드+컴포넌트 단위로 확인하고 통합은 `NEXT_PUBLIC_API_URL`(develop 배포) 대상. result/page는 Task 4·5가 함께 빌드 통과해야 하므로, 단독 task 빌드가 깨지면 4·5를 연속 실행.
