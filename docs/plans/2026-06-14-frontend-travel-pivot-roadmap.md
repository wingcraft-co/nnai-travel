# 프론트엔드 여행 전환 로드맵 (Frontend Travel Pivot)

> **For agentic workers:** 이 문서는 **로드맵(분해 + 아키텍처 결정)**이다. 실제 구현은 각 하위 Phase의 상세 plan 문서를 `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`로 task-by-task 실행한다.

**Goal:** 백엔드 여행 전환(Phase 1~6, 완료)에 맞춰 프론트엔드를 이민 서비스 → 휴가 여행지 추천 + 협업 플래너로 전환한다.

**현재 상태 (2026-06-14):**
- ✅ 백엔드: `/api/travel/recommend`(결정론적 추천), `/api/travel/itinerary`(LLM 일정), `/api/trips/*`(Trip·초대·plan-items) 전부 구현·커밋·푸시.
- ❌ 프론트엔드: 여전히 이민 서비스. BFF(`recommend`/`reveal`/`detail`/`guide`)·페이지(`onboarding/form`, `result`, `guide/[city_id]`)가 이민용이고 여행 백엔드에 연결된 화면 없음.
- ✅ `frontend/src/data/destinations.json` 복사본은 이미 존재(Phase 1에서 동기화).

---

## 격리/원칙 (필수)

- **CLAUDE.md 규칙 준수:** frontend 작업 시 백엔드 API 스키마 변경 금지(이미 확정된 여행 API 계약 사용). 엔드포인트/스키마는 `cowork/backend/api-reference.md`가 단일 진실 공급원.
- **Next.js 16 주의:** `frontend/AGENTS.md` — 훈련 데이터와 다를 수 있으므로 코드 작성 전 `node_modules/next/dist/docs/` 확인.
- **디자인 시스템:** tweakcn Amber Mono 2.0, CSS 변수만 사용(HEX 금지). 타로 카드는 `docs/designs/tarot-card-design.md` 준수.
- **테스트 패턴:** UI 페이지는 단위 테스트 없음. **순수 로직(BFF enrichment, draft, content 헬퍼)을 `src/lib/`로 추출해 `*.test.mjs`로 검증** — 기존 `onboarding-form-draft.test.mjs` 패턴을 따른다.
- push는 항상 `develop`. `main` 금지.
- 작업 로그는 루트 `tasklist.md`.

---

## 핵심 아키텍처 결정

### 1. recommend 흐름: 카드 세션/reveal 제거 → 직접 추천

이민 백엔드는 `recommend`(5장 카드 세션 생성) → `reveal`(3장 선택 공개)의 **2단계 세션 모델**이었다.
여행 백엔드 `/api/travel/recommend`는 **세션 없이 `top_destinations`를 직접 반환**한다(`reveal` 엔드포인트 없음).

**결정:**
- 프론트엔드는 `/api/travel/recommend`를 호출해 받은 `top_destinations`(기본 5개)를 타로 카드로 표시.
- **타로 UX는 유지하되 reveal 의미를 클라이언트 사이드로 이동:** 카드를 뒷면으로 깔고 → 사용자가 카드를 뒤집어(flip) 공개하는 애니메이션은 그대로. 단, 서버 round-trip 없이 이미 받은 데이터로 flip만 수행.
- **"3장 선택" → "1곳 선택해 일정 생성":** `/api/travel/itinerary`는 단일 destination을 받으므로, 카드 선택의 종착점은 "이 여행지로 N박M일 일정 만들기"(Phase 8) 또는 "Trip으로 저장"(Phase 9)이다.
- `src/app/api/reveal/route.ts`는 여행 흐름에서 미사용 → Phase 7에서 제거(또는 이민 흐름 잔존 시 보류는 self-review에서 판단).

### 2. enrichment 소스 교체: city_scores/visa_db → destinations.json

기존 `recommend`/`reveal` BFF는 응답을 `city_scores.json`+`visa_db.json`(비자/노마드 점수)으로 enrich했다.
여행 추천 응답(`top_destinations`)은 이미 `destinations.json` 기반이고 `vibe/best_months/activities/must_see/est_cost_krw` 등 여행 필드를 백엔드가 채워서 반환한다.

**결정:**
- 여행 recommend BFF는 **백엔드 응답을 거의 그대로 통과**시키되, 카드 표시에 필요한 보조 필드(예: `city_description`, 국기용 `country_id`는 이미 있음)만 `destinations.json`에서 보강.
- enrichment 로직은 `src/lib/destination-enrich.ts`(순수 함수)로 추출하고 `.test.mjs`로 검증.

### 3. 입력 폼: 이민 필드 → 여행 필드

`onboarding/form`의 `FormData`(immigration_purpose/timeline/stay_style/income_range/tax_sensitivity...) →
여행 입력(`travel_month`, `nights`, `budget_krw`, `interests[]`, `persona`, `preferred_regions[]`, `companions{type,headcount,ages,accessibility,pace}`)으로 교체.

**결정:** 5스텝 구조·`SelectCard`·`ProgressBar`·draft 자동저장 패턴은 유지하고 **스텝 내용만 교체**. 퀴즈(persona 진단)는 결과 persona를 여행 추천 `persona`로 매핑.

---

## 하위 Phase 분해

각 Phase는 독립적으로 동작·테스트 가능한 단위다. 순서대로 진행 권장(7 → 8 → 9).

| Phase | 내용 | 주요 파일 | 의존 |
|-------|------|-----------|------|
| **7. 여행 입력 + 추천 흐름** | 입력폼·BFF·타로 결과를 여행으로 전환 | `onboarding/form`, `api/recommend`, `lib/destination-enrich`, `result/page`, `components/tarot/*` | 없음(독립) |
| **8. 일정 상세 (itinerary)** | 선택 여행지 → N박M일 LLM 일정 화면 | `api/detail`→`api/itinerary`, `guide/[city_id]`→`itinerary` 페이지 | Phase 7(추천 결과에서 진입) |
| **9. Trip & 협업 플래너 UI** | Trip 생성·초대·합류·공동 plan-items 편집 | `app/[locale]/trips/*`(신규), `api/trips/*` BFF(신규) | Phase 7~8(여행지/일정에서 Trip 생성) |

### Phase 7 — 여행 입력 + 추천 흐름 (상세 plan: `2026-06-14-phase7-frontend-travel-recommend.md`)

- **입력폼:** `FormData` 여행 필드 교체, 5스텝 카피/옵션 교체, draft 헬퍼(`onboarding-form-draft.ts`) 여행 스키마로 갱신.
- **추천 BFF:** `api/recommend/route.ts` → `/api/travel/recommend` 호출 + `destination-enrich`. body는 폼 → 여행 추천 request로 변환.
- **타로 결과:** `result/page.tsx`가 `top_destinations`를 소비, `TarotDeck`/`TarotCard`/`CityCompare`가 여행지 필드(vibe/best_months/est_cost_krw/activities) 표시.
- **i18n:** `ko.json`/`en.json` 여행 카피 추가.
- **테스트:** `destination-enrich.test.mjs`, 갱신된 `onboarding-form-draft.test.mjs`, 여행 추천 request 매핑 헬퍼 테스트.

### Phase 8 — 일정 상세 (itinerary)

- **BFF:** `api/detail/route.ts` → `api/itinerary/route.ts`로 신설, `/api/travel/itinerary` 호출(destination + travel_profile body). 기존 detail은 이민 흐름 제거 시 함께 정리.
- **페이지:** `guide/[city_id]` → `itinerary`(또는 `result`에서 인라인 라이트박스). N박M일 마크다운 렌더링(Day별), 기존 마크다운 렌더 유틸 재사용.
- **상태 전달:** 선택 destination + travel_profile을 sessionStorage 또는 라우트 state로 전달.
- **테스트:** itinerary request 빌더 헬퍼, 마크다운 렌더 헬퍼.

### Phase 9 — Trip & 협업 플래너 UI

- **BFF:** `api/trips/*` route(신규) — `/api/trips`, `/api/trips/{id}`, `/invites`, `/join`, `/plan-items` 프록시(쿠키 세션 전달).
- **페이지:** `trips`(목록), `trips/[id]`(상세 + 멤버 + 공동 일정 편집), `trips/join`(초대 토큰 합류).
- **협업 플래너:** plan-items CRUD UI, 카테고리(관광·식사·이동·숙소·액티비티·기타), Day별 그룹·정렬, 권한(추가/조회=멤버, 수정/삭제=작성자 또는 owner). 실시간 대신 폴링/수동 새로고침(YAGNI).
- **진입점:** 추천 카드/일정 화면 → "Trip으로 저장" → 초대 링크 공유.
- **테스트:** plan-items 정렬/카테고리/권한 표시 순수 헬퍼.

---

## 문서 동기화 (각 Phase 완료 시)

- 백엔드 스키마 변경 없음(여행 API는 이미 확정) → `api-reference.md`/`db-schema.md` 갱신 불필요.
- 새 `*.test.mjs`는 CI(`.github/workflows/main-tests.yml`)의 프론트 테스트 목록에 등록(해당 워크플로의 frontend job 패턴 확인).
- 작업 로그 → `tasklist.md`.

## 비범위 (YAGNI)

- 실시간 협업(WebSocket/CRDT) — 폴링/수동 새로고침으로 충분.
- 여행 추천에 결제/rate-limit 게이팅 — 백엔드 미적용 상태, 추후 별도 협의.
- 이민 흐름과의 동시 운영(피처 플래그) — 전환이 원칙이므로 이민 화면은 단계적으로 제거.
