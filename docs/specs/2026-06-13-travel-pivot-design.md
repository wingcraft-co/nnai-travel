# 설계: "운명의 여행지" — AI 여행지 추천 + 협업 여행 플래너

작성일: 2026-06-13
상태: 승인됨 (구현 대기)

## 배경

기존 NomadNavigator AI(NNAI)는 디지털 노마드 장기 이민 설계 서비스다.
이 프로젝트(`nnai-travel`)는 NNAI를 fork한 **별도 저장소**(`wingcraft-co/nnai-travel.git`)이며,
동일한 2단계 추천 아키텍처와 타로 카드 UX를 재활용해 **휴가 여행지 추천 + 협업 여행 플래너**로 전환한다.

### 격리 원칙 (필수)

- 코드 저장소: `nnai-travel.git` (원본 `nnai.git`과 분리)
- DB/인프라: Railway `nnai-travel-prd` 환경 + 별도 PostgreSQL (원본과 분리)
- push는 항상 `develop`. `main`은 명시 지시 시에만.
- 원본 nnai의 코드/DB/데이터에 어떤 영향도 주지 않는다.

## 제품 컨셉 (3요소 통합)

기존 NNAI의 퀴즈 → 타로 → 상세 흐름에 셋을 layering한다.

```
[퀴즈] 여행 성향 진단        → 페르소나 (온보딩)
        ↓
[타로] 운명의 여행지 5장      → 3장 선택 → reveal (Step 1, 규칙기반 추천)
        ↓
[플래너] N박M일 일정 생성     → 도시별 여행 가이드 (Step 2, LLM)
        ↓
[협업] Trip 저장 → 동행 초대 → 공동 일정 작성
```

- **퀴즈**: `onboarding/quiz` 자산 재사용 → 여행 성향 진단 (예: 액티브 탐험가 / 힐링 휴양러 / 미식 탐험가 / 문화 수집가 / 인생샷 헌터)
- **타로**: `components/tarot/` 그대로 → "운명의 여행지" 메타포 (카피만 이민→여행 교체)
- **플래너**: Step 2 LLM이 이민 가이드 대신 N박M일 일정표 생성
- **협업**: 추천 보고서를 Trip으로 저장하고 동행을 초대해 공동으로 일정 항목을 추가

## 아키텍처 — 유지 / 교체

| 영역 | 처리 |
|------|------|
| **유지** | 2단계 파이프라인(recommend→reveal→detail), 타로 UX, 퀴즈 흐름, i18n(ko/en), 인증(Google OAuth), 결제/rate limit, 디자인 시스템(Amber Mono), 규칙기반 추천 골격 |
| **데이터 재설계** | `visa_db.json`(비자/세금) → `destinations.json`(시즌/항공/안전/액티비티). `city_scores.json`을 여행 필드로 re-schema |
| **추천엔진 교체** | `recommender.py` 블록 A~D를 여행 적합도(시즌매칭·예산핏·성향매칭·인기/안전)로 재작성 + 동행 프로필 블록 추가 |
| **프롬프트 교체** | `prompts/system.py`의 비자/세금/쉥겐 경고 → 여행 시즌·예산·일정 가이드 |
| **유틸 교체** | `tax_warning`/`planb`/`schengen_calculator` → `season_advisor`/`budget_estimator`/`itinerary` |
| **프론트 카피** | "이민 설계" → "여행 설계", 입력폼: 소득/체류 → 여행기간/예산/동행 |
| **신규 협업** | trips/members/invites/plan_items 테이블 + 초대 링크 + 공동 플래너 UI |

## 입력 데이터 모델

### 여행 기본 입력

- `여행기간`: N박M일
- `예산`: 1인 총액 (KRW)
- `출발지`: 도시/공항
- `관심사`: 자연 / 미식 / 액티비티 / 문화 / 휴양 / 쇼핑 / 인생샷 (다중)
- `선호 권역`: 동남아 / 동북아 / 유럽 / 미주 / 무관 등
- `여행 성향`: 퀴즈 결과(페르소나)

### 동행 프로필 (companions)

```
companions: {
  type:          "혼자 | 커플(허니문) | 가족 | 친구그룹 | 효도여행 | 회사/단체",
  headcount:     동행 인원 수,
  ages:          ["유아", "초등", "청소년", "성인", "60대+"],   // 다중
  accessibility: ["유모차", "휠체어", "없음"],                  // 특수 니즈
  pace:          "빡빡하게 많이 | 여유롭게 적당히 | 휴양 위주"
}
```

동행 신호가 추천에 반영되는 방식:

- **아이 동반** → 키즈프렌들리/안전/짧은 비행시간 가중, 장거리·고위험 지역 감점
- **허니문(커플)** → 로맨틱 분위기·프라이빗 숙소·미식 가중
- **효도여행/60대+** → 접근성·휴양·완만한 페이스·의료 인프라 가중
- **친구그룹** → 나이트라이프·액티비티·인스타 스팟 가중
- **접근성 니즈(유모차/휠체어)** → 접근성 낮은 목적지 hard filter 또는 강한 감점

→ 퀴즈 페르소나(개인 성향) × 동행 프로필(그룹 제약)을 **둘 다** 반영.

### 목적지 데이터 (destinations)

기존 52개 도시를 재활용하되 여행 필드 추가:

- `best_months`: 추천 방문 시기 (월 배열)
- `peak_season`: 성수기 여부/시기
- `avg_flight_hours`: 출발지(서울 기준) 평균 비행시간
- `budget_tier`: 저 / 중 / 고
- `activities[]`: 가능한 액티비티 태그
- `vibe`: 휴양 / 도시 / 모험 / 문화 등
- `safety`: 안전 점수 (기존 재활용)
- `must_see[]`: 대표 관광 스팟
- `kid_friendly`, `romantic`, `accessibility_score`, `nightlife`: 동행 매칭 필드

## 협업 흐름 (Trip & 초대)

```
[추천 완료] 운명의 여행지 TOP3 + 보고서
        ↓
[Trip 생성] 보고서를 Trip으로 저장 (소유자 = 본인)
        ↓
[초대] 초대 링크 발급 → 친구가 링크로 합류 (Google 로그인)
        ↓
[공동 플래너] 멤버들이 Day별 계획 항목을 하나씩 추가
   - 항목: Day / 시간 / 장소 / 카테고리(관광·식사·이동·숙소) / 추가한 사람 / 메모
   - 보고서의 추천 스팟을 '계획에 담기' 한 번에 추가
   - (옵션) 멤버 투표 👍 로 합의
```

협업은 실시간(CRDT)이 아니라 **DB 기반 공유 + 새로고침/폴링**. 초대는 이메일 발송 없이 **초대 링크 + 기존 Google 로그인**.

### 신규 DB 엔티티 (utils/db.py `init_db()` DDL)

| 테이블 | 핵심 컬럼 |
|--------|----------|
| `trips` | id, owner_user_id, destination(보고서 스냅샷 JSON), start_date, end_date, created_at |
| `trip_members` | trip_id, user_id, role(owner/member), joined_at |
| `trip_invites` | trip_id, token, expires_at, used_at, created_by |
| `trip_plan_items` | id, trip_id, day, time, place, category, added_by, memo, created_at |
| `trip_plan_votes` | (옵션) plan_item_id, user_id, created_at |

- 스키마는 `init_db()`에 멱등 DDL(`CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ... IF NOT EXISTS`)로 추가 → 배포 시 자동 반영.
- `cowork/backend/db-schema.md` 동기화 필수.

## Phase 구성 (각 단계 독립 spec → plan → 구현)

| Phase | 내용 | DB |
|-------|------|-----|
| **1. 데이터 모델** | destinations.json 여행 스키마 + 52개 도시 여행/동행 필드 + sync 스크립트 | 불필요(JSON) |
| **2. 추천엔진** | recommender.py 여행 스코어링 + 동행 프로필 블록 재작성 + 테스트 | 불필요 |
| **3. LLM 플래너** | Step 2 N박M일 일정 가이드 프롬프트(system.py/builder.py) | 불필요 |
| **4. 프론트 코어** | 카피/입력폼(여행기간·예산·동행)·퀴즈·타로 결과 여행 전환 | 불필요 |
| **5. Trip & 초대** | trips/members/invites 테이블 + 초대 링크 + API | 필요 |
| **6. 공동 플래너** | trip_plan_items + 협업 일정 UI | 필요 |

Phase 1~4는 JSON 기반이라 DB/Railway 설정과 무관하게 진행 가능. DB는 Phase 5부터.

## 테스트 전략

- 백엔드: `SKIP_EXTERNAL_INIT=1 pytest tests/` — 추천엔진은 규칙 기반이라 결정적(deterministic) 테스트 가능
- 새 테스트 파일은 `.github/workflows/main-tests.yml`에 등록 (CLAUDE.md 규칙)
- 프론트: 기존 `.test.mjs` 패턴 따름

## 문서 동기화 (CLAUDE.md 규칙)

- 엔드포인트/스키마 변경 → `cowork/backend/api-reference.md`
- DB 테이블/컬럼 변경 → `cowork/backend/db-schema.md`
- rawdata CSV → JSON 동기화 → `scripts/sync_nomaddb_csv_to_json.py` 패턴 참고
- 작업 로그 → 루트 `tasklist.md`

## 비범위 (YAGNI)

- 실시간 협업(CRDT/WebSocket) — 폴링으로 충분
- 이메일 초대 발송 — 초대 링크로 대체
- 항공권/숙소 실시간 예약 연동 — 딥링크 수준만
- 결제 모델 재설계 — 기존 인프라 유지(필요 시 후속)
