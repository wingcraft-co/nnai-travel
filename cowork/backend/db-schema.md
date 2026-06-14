# NomadNavigator AI — DB Schema Reference

> 프론트엔드 개발자용 데이터베이스 스키마 레퍼런스
> DB: PostgreSQL (Railway)
> 정의 위치: `utils/db.py` → `init_db()`
> 최종 업데이트: 2026-05-25 (단건 결제 모델 컬럼 추가)

운영 메모:
- 스키마 보장 시점은 FastAPI startup (`server.py`) 입니다.
- startup은 `utils.db.ensure_database_ready()`로 핵심 테이블/컬럼 존재 여부를 먼저 확인합니다.
- 이미 준비된 DB에서는 DDL을 실행하지 않고, 비어 있거나 구버전인 DB에서만 advisory lock 후 `utils.db.init_db()`를 실행합니다.
- `server` 모듈 import만으로는 DB 연결/DDL이 실행되지 않습니다.
- DB를 완전히 비운 직후 수동 초기화가 필요하면 `python scripts/init_db.py`를 실행합니다.

---

## 테이블 목록

| 테이블 | 설명 |
|--------|------|
| `users` | Google OAuth 로그인 유저 |
| `auth_sessions` | 웹 로그인 opaque session 저장소 |
| `billing_entitlements` | 웹 entitlement / plan 상태 |
| `billing_checkout_sessions` | 결제 provider checkout 생성/완료 추적 |
| `report_purchases` | 도시별 유료 보고서 구매 기록 |
| `billing_usage_ledger` | pay-as-you-go 사용량 ledger |
| `billing_provider_events` | billing provider webhook 멱등 처리 |
| `detail_guide_cache` | 상세 가이드 LLM 응답 캐시 + 단건 결제 보유 보고서 기록 (`city_id`, `is_free`) |
| `tarot_sessions` | 타로 카드 5장 추천 결과 + reveal 게이팅 (TTL 24시간) |
| `nomad_journey_stops` | 지원 도시 또는 검증된 여행 로그용 위치로 저장한 노마드 여정 stop |
| `trips` | 저장된 여행(추천 보고서 스냅샷) |
| `trip_members` | 여행 멤버 + 역할(owner/member) |
| `trip_invites` | 여행 초대 링크 토큰(만료 14일) |
| `trip_plan_items` | 공동 여행 계획 항목(Day별 장소·카테고리) |
| `visits` | 경로별 방문자 수 집계 |
| `user_city_plans` | Pro 대시보드 활성 도시 플랜 |
| `dashboard_widget_settings` | Pro 대시보드 위젯 설정 |
| `onboarding_drafts` | 로그인 사용자별 온보딩 폼/퀴즈 임시 저장본 |
| `verified_sources` | 검증 데이터 출처(소스) 목록 |
| `verified_countries` | 검증된 국가별 비자 데이터 |
| `verified_cities` | 검증된 도시별 노마드 지표 데이터 |
| `verified_city_sources` | 도시-소스 연결 (N:M) |
| `verification_logs` | 데이터 검증 작업 이력 |

---

## users

Google OAuth 콜백 시 자동 upsert됩니다.

```sql
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,   -- Google OAuth sub (유저 고유 ID)
    email      TEXT,               -- 구글 이메일
    name       TEXT,               -- 구글 이름
    picture    TEXT,               -- 프로필 이미지 URL
    persona_type TEXT,             -- nnai 표준 페르소나 타입
    created_at TEXT,               -- ISO 8601 타임스탬프 (UTC)
    email_enc  BYTEA,              -- 이메일 암호화본 (application-level encryption)
    email_sha256 TEXT,             -- 이메일 검색/중복확인용 hash
    name_enc   BYTEA,              -- 이름 암호화본 (application-level encryption)
    free_report_city_id TEXT,      -- 무료 보고서를 1회 부여받은 도시 id (NULL이면 미사용)
    free_report_used_at TIMESTAMPTZ -- 무료 보고서 부여 시각
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | TEXT PK | Google OAuth `sub` 값 |
| `email` | TEXT | 레거시 평문 이메일 컬럼. 신규 OAuth upsert는 `NULL`로 유지하고 과거 레코드 호환에만 사용 |
| `name` | TEXT | 레거시 평문 이름 컬럼. 신규 OAuth upsert는 `NULL`로 유지하고 과거 레코드 호환에만 사용 |
| `picture` | TEXT | 구글 프로필 이미지 URL |
| `persona_type` | TEXT | `wanderer|local|planner|free_spirit|pioneer` |
| `created_at` | TEXT | 최초 로그인 시각 (ISO 8601 UTC) |
| `email_enc` | BYTEA | 이메일 암호화본 |
| `email_sha256` | TEXT | 이메일 hash |
| `name_enc` | BYTEA | 이름 암호화본 |
| `free_report_city_id` | TEXT | 단건 결제 모델(2026-05-25): 무료 보고서 1회 부여받은 도시 id. NULL이면 미사용. 한 번 설정되면 변경 불가 |
| `free_report_used_at` | TIMESTAMPTZ | 무료 보고서 부여 시각 |

**참고:** 재로그인 시 picture 및 encrypted copy는 갱신됩니다. 신규 OAuth upsert는 raw `email`, `name` 평문을 더 이상 저장하지 않습니다. 앱 시작 시 기존 레거시 plain `email`/`name` 레코드도 encrypted copy로 백필한 뒤 `NULL` 처리합니다.

---

## auth_sessions

웹 로그인용 opaque session 저장소입니다. `nnai_session` 쿠키에는 사용자 프로필 대신 서명된 `session_id`만 저장됩니다.

```sql
CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `session_id` | TEXT PK | opaque session 식별자 |
| `user_id` | TEXT FK | `users.id` 참조 |
| `created_at` | TIMESTAMPTZ | 세션 생성 시각 |
| `expires_at` | TIMESTAMPTZ | 세션 만료 시각 |
| `revoked_at` | TIMESTAMPTZ | 로그아웃/무효화 시각 |

운영 메모:
- `revoked_at IS NULL` 이고 `expires_at > NOW()` 인 세션만 유효합니다.
- 로그아웃 시 쿠키 삭제와 함께 DB 세션도 revoke 됩니다.

---

## billing_entitlements

웹 rate limiting / billing entitlement의 기준 테이블입니다. row가 없어도 앱은 기본적으로 `free`로 해석합니다.

```sql
CREATE TABLE IF NOT EXISTS billing_entitlements (
    user_id                TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    plan_tier              TEXT NOT NULL CHECK (plan_tier IN ('free', 'pro')),
    status                 TEXT NOT NULL CHECK (status IN ('active', 'past_due', 'canceled', 'grace')),
    payg_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
    payg_monthly_cap_usd   NUMERIC(10,2) NOT NULL DEFAULT 50.00,
    current_period_start   TIMESTAMPTZ,
    current_period_end     TIMESTAMPTZ,
    provider               TEXT,
    provider_customer_id   TEXT,
    provider_subscription_id TEXT,
    plan_code              TEXT NOT NULL DEFAULT 'free',
    cancel_at_period_end   BOOLEAN NOT NULL DEFAULT FALSE,
    grace_until            TIMESTAMPTZ,
    last_webhook_at        TIMESTAMPTZ,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | TEXT PK/FK | `users.id` 참조 |
| `plan_tier` | TEXT | `free` 또는 `pro` |
| `status` | TEXT | `active`, `past_due`, `canceled`, `grace` |
| `payg_enabled` | BOOLEAN | pay-as-you-go 사용 여부 |
| `payg_monthly_cap_usd` | NUMERIC(10,2) | 월 상한, 기본 `50.00` |
| `current_period_start` | TIMESTAMPTZ | 현재 과금 주기 시작 |
| `current_period_end` | TIMESTAMPTZ | 현재 과금 주기 종료 |
| `provider` | TEXT | 현재 entitlement의 provider, 현재는 `polar` |
| `provider_customer_id` | TEXT | Polar customer ID |
| `provider_subscription_id` | TEXT | Polar subscription ID |
| `plan_code` | TEXT | 내부 결제 플랜 코드. 현재 `pro_monthly` 중심 |
| `cancel_at_period_end` | BOOLEAN | 기간 종료 시 취소 예약 여부 |
| `grace_until` | TIMESTAMPTZ | past_due 시 유예 만료 시각 |
| `last_webhook_at` | TIMESTAMPTZ | 마지막 webhook 반영 시각 |
| `updated_at` | TIMESTAMPTZ | 마지막 갱신 시각 |

---

## billing_checkout_sessions

checkout 생성 이후 결제 완료 검증 및 복구/추적에 사용하는 테이블입니다.

```sql
CREATE TABLE IF NOT EXISTS billing_checkout_sessions (
    id                   BIGSERIAL PRIMARY KEY,
    user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider             TEXT NOT NULL,
    provider_checkout_id TEXT UNIQUE,
    plan_code            TEXT NOT NULL,
    city_id              TEXT,
    amount_krw           INTEGER,
    status               TEXT NOT NULL CHECK (status IN ('created', 'completed', 'expired', 'failed')),
    return_path          TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at         TIMESTAMPTZ
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BIGSERIAL PK | 내부 checkout row ID |
| `user_id` | TEXT FK | `users.id` 참조 |
| `provider` | TEXT | 결제 provider (`portone`, `polar`) |
| `provider_checkout_id` | TEXT | provider checkout/payment ID. PortOne은 `paymentId`, Polar는 checkout ID |
| `plan_code` | TEXT | 내부 플랜 코드 |
| `city_id` | TEXT | 도시 보고서 단건 결제 대상 city_id |
| `amount_krw` | INTEGER | PortOne 결제 검증용 원화 결제 예정 금액 |
| `status` | TEXT | `created`, `completed`, `expired`, `failed` |
| `return_path` | TEXT | 프론트 복귀 경로 |
| `created_at` | TIMESTAMPTZ | checkout 생성 시각 |
| `completed_at` | TIMESTAMPTZ | 완료 처리 시각 |

---

## report_purchases

도시별 유료 보고서 구매 권한의 단일 진실 공급원입니다. 무료 보고서 사용 기록은 `users.free_report_city_id`, 실제 보고서 캐시는 `detail_guide_cache`에 남지만, 유료 구매 여부는 이 테이블로 판단합니다.

```sql
CREATE TABLE IF NOT EXISTS report_purchases (
    id                  BIGSERIAL PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city_id             TEXT NOT NULL,
    provider            TEXT NOT NULL,
    provider_payment_id TEXT NOT NULL,
    amount_krw          INTEGER,
    purchased_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_payment_id),
    UNIQUE (user_id, city_id)
);

CREATE INDEX IF NOT EXISTS idx_report_purchases_user_city
ON report_purchases(user_id, city_id);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BIGSERIAL PK | 내부 구매 row ID |
| `user_id` | TEXT FK | `users.id` 참조 |
| `city_id` | TEXT | 구매한 도시 보고서 ID |
| `provider` | TEXT | 결제 provider (`portone`, `polar`) |
| `provider_payment_id` | TEXT | provider 결제 ID. PortOne은 `paymentId` |
| `amount_krw` | INTEGER | 결제 금액(KRW). 글로벌 provider에서는 NULL 가능 |
| `purchased_at` | TIMESTAMPTZ | 구매 확정 시각 |

---

## billing_usage_ledger

pay-as-you-go 사용량을 endpoint 단위로 기록하는 append-oriented ledger입니다.

```sql
CREATE TABLE IF NOT EXISTS billing_usage_ledger (
    id                   BIGSERIAL PRIMARY KEY,
    user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint             TEXT NOT NULL CHECK (endpoint IN ('recommend', 'detail')),
    request_key          TEXT NOT NULL,
    usage_type           TEXT NOT NULL CHECK (usage_type IN ('subscription', 'payg')),
    estimated_cost_usd   NUMERIC(10,4) NOT NULL DEFAULT 0,
    billed_cost_usd      NUMERIC(10,4),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (request_key)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BIGSERIAL PK | ledger row ID |
| `user_id` | TEXT FK | `users.id` 참조 |
| `endpoint` | TEXT | `recommend` 또는 `detail` |
| `request_key` | TEXT | 요청 멱등성 키 |
| `usage_type` | TEXT | 현재는 `payg` 중심 사용 |
| `estimated_cost_usd` | NUMERIC(10,4) | 사전 추정 비용 |
| `billed_cost_usd` | NUMERIC(10,4) | 실제 청구 비용(선택) |
| `created_at` | TIMESTAMPTZ | ledger 생성 시각 |

---

## billing_provider_events

checkout/webhook 공급자 이벤트의 멱등성 보장을 위한 audit 테이블입니다.

```sql
CREATE TABLE IF NOT EXISTS billing_provider_events (
    id              BIGSERIAL PRIMARY KEY,
    provider        TEXT NOT NULL,
    event_id        TEXT NOT NULL,
    payload_digest  TEXT NOT NULL,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, event_id)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BIGSERIAL PK | event row ID |
| `provider` | TEXT | billing provider 식별자 |
| `event_id` | TEXT | provider event 고유 ID |
| `payload_digest` | TEXT | payload hash/digest |
| `processed_at` | TIMESTAMPTZ | 처리 시각 |

---

## detail_guide_cache

Step 2 상세 가이드 markdown 캐시 + 단건 결제 모델(2026-05-25) 보유 보고서 기록을 겸합니다. 같은 로그인 사용자, 같은 온보딩 프로필, 같은 선택 도시에 대해 LLM을 최초 1회만 호출하고 이후에는 캐시된 markdown을 반환합니다. `city_id` + `is_free` 컬럼을 통해 무료 부여 / 결제 완료 보고서를 구분합니다.

```sql
CREATE TABLE IF NOT EXISTS detail_guide_cache (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cache_key       TEXT NOT NULL,
    markdown        TEXT NOT NULL,
    parsed_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    city_snapshot   JSONB NOT NULL DEFAULT '{}'::jsonb,
    city_id         TEXT,                          -- 도시 id (lowercase + hyphen). frontend `normalizeCityId` 규칙과 일치
    is_free         BOOLEAN NOT NULL DEFAULT FALSE, -- TRUE면 무료 부여 (워터마크+블러). FALSE면 결제 완료
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, cache_key)
);
CREATE INDEX IF NOT EXISTS idx_detail_guide_cache_user_city
ON detail_guide_cache(user_id, city_id);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | TEXT FK | `users.id` 참조 |
| `cache_key` | TEXT | `_user_profile + selected_city` canonical JSON의 SHA-256 |
| `markdown` | TEXT | 캐시된 상세 가이드 markdown (무료/유료 동일 콘텐츠) |
| `parsed_snapshot` | JSONB | 요청 당시 Step 1 parsed 데이터 스냅샷 |
| `city_snapshot` | JSONB | 선택 도시 스냅샷 |
| `city_id` | TEXT | 도시 식별자. `users.free_report_city_id`와 `library_guides` 조회에 사용. 과거 데이터는 NULL일 수 있음 |
| `is_free` | BOOLEAN | TRUE = 무료 부여 (프론트가 워터마크+블러+다운로드 잠금). FALSE = 결제 완료. 결제 시 같은 row의 is_free가 FALSE로 다운그레이드 |

---

## tarot_sessions

`/api/recommend` 응답으로 발급되는 타로 카드 5장 세션 저장소입니다. 사용자가 `/api/reveal`로 3장을 선택할 때까지 추천 결과를 서버사이드에 보관하여 임의 reveal을 차단합니다. 비로그인 사용자도 사용 가능하므로 `user_id` FK는 없습니다.

```sql
CREATE TABLE IF NOT EXISTS tarot_sessions (
    session_id        TEXT PRIMARY KEY,
    cities            JSONB NOT NULL,
    revealed_indices  JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tarot_sessions_expires_at
ON tarot_sessions(expires_at);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `session_id` | TEXT PK | NOT NULL | 16자 hex (uuid4 prefix) |
| `cities` | JSONB | NOT NULL | 추천 도시 5장 원본 데이터 |
| `revealed_indices` | JSONB | NULL 가능 | 사용자가 선택해 공개한 3장 indices (정렬됨). 미공개면 `NULL` |
| `created_at` | TIMESTAMPTZ | NOT NULL | 세션 생성 시각 (기본값: NOW()) |
| `expires_at` | TIMESTAMPTZ | NOT NULL | 세션 만료 시각 (기본 TTL 24시간) |

운영 메모:
- `expires_at > NOW()` row만 유효합니다.
- `create_session` 호출 시 만료된 row가 자동 정리됩니다 (lazy cleanup, 별도 cron 불필요).
- `reveal_cards`는 `SELECT ... FOR UPDATE`로 잠금을 잡고 `revealed_indices`가 `NULL`일 때만 갱신합니다 (중복 reveal 차단).
- TTL은 `api.tarot_session.SESSION_TTL_SECONDS` 상수로 조정합니다.

---

## nomad_journey_stops

픽셀 지구본 이스터에그에서 사용자가 확정한 도시 중심 좌표를 저장합니다. 지원 도시는 `solid`, 미지원 검증 도시는 여행 로그용 위치로 저장되어 `dashed` 선 렌더링에 사용됩니다. Legacy 좌표 직접 저장 row는 개인 여정에는 남지만 public community 집계에서는 제외됩니다. 기존 `pins` 테이블은 제거되며 데이터는 마이그레이션하지 않습니다.

```sql
DROP TABLE IF EXISTS pins;

CREATE TABLE IF NOT EXISTS nomad_journey_stops (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city            TEXT NOT NULL,
    country         TEXT NOT NULL,
    country_code    TEXT,
    lat             DOUBLE PRECISION NOT NULL,
    lng             DOUBLE PRECISION NOT NULL,
    note            TEXT NOT NULL CHECK (char_length(note) <= 10),
    persona_type    TEXT,
    verified_method TEXT NOT NULL DEFAULT 'gps_city_confirmed',
    supported_city_id TEXT,
    is_supported_city BOOLEAN NOT NULL DEFAULT FALSE,
    location_source TEXT NOT NULL DEFAULT 'legacy',
    line_style TEXT NOT NULL DEFAULT 'solid',
    geocode_place_id TEXT,
    geocode_confidence DOUBLE PRECISION,
    geocoded_at TIMESTAMPTZ,
    gps_verified BOOLEAN NOT NULL DEFAULT FALSE,
    flag_color TEXT NOT NULL DEFAULT 'red',
    github_issue_url TEXT,
    github_issue_key TEXT,
    github_issue_status TEXT NOT NULL DEFAULT 'not_required',
    CHECK (lat BETWEEN -90 AND 90),
    CHECK (lng BETWEEN -180 AND 180),
    CHECK (line_style IN ('solid', 'dashed')),
    CHECK (flag_color IN ('green', 'red', 'yellow')),
    CHECK (github_issue_status IN ('not_required', 'created', 'linked', 'failed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_user_created
ON nomad_journey_stops(user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_city
ON nomad_journey_stops(city, country);

CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_persona
ON nomad_journey_stops(persona_type);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | SERIAL PK | NOT NULL | 자동 증가 정수 ID |
| `user_id` | TEXT FK | NOT NULL | `users.id` 참조, 유저 삭제 시 함께 삭제 |
| `city` | TEXT | NOT NULL | 인증한 도시명 |
| `country` | TEXT | NOT NULL | 인증한 국가명 |
| `country_code` | TEXT | NULL 가능 | ISO-2 국가 코드 |
| `lat` | DOUBLE PRECISION | NOT NULL | 도시 중심 위도 |
| `lng` | DOUBLE PRECISION | NOT NULL | 도시 중심 경도 |
| `note` | TEXT | NOT NULL | 10글자 이하 개인 방명록 |
| `persona_type` | TEXT | NULL 가능 | 저장 시점의 NNAI 노마드 타입 |
| `verified_method` | TEXT | NOT NULL | `gps_city_confirmed`, `nnai_supported_city_selected`, `backend_geocoded_unsupported` |
| `supported_city_id` | TEXT | NULL 가능 | NNAI 지원 도시 ID. 미지원/legacy는 `NULL` |
| `is_supported_city` | BOOLEAN | NOT NULL | NNAI 지원 도시 여부 |
| `location_source` | TEXT | NOT NULL | `legacy`, `nnai_supported`, `nominatim` |
| `line_style` | TEXT | NOT NULL | 지도 연결선 스타일. `solid` 또는 `dashed` |
| `geocode_place_id` | TEXT | NULL 가능 | 외부 geocoder place id |
| `geocode_confidence` | DOUBLE PRECISION | NULL 가능 | 외부 geocoder confidence/importance |
| `geocoded_at` | TIMESTAMPTZ | NULL 가능 | 백엔드 geocoding 검증 시각 |
| `gps_verified` | BOOLEAN | NOT NULL | 사용자가 선택 도시 근처 GPS 인증을 완료했는지 여부 |
| `flag_color` | TEXT | NOT NULL | 깃발 색상. `green`, `red`, `yellow` |
| `github_issue_url` | TEXT | NULL 가능 | 미지원 GPS 인증 도시의 GitHub 추가 요청 이슈 URL |
| `github_issue_key` | TEXT | NULL 가능 | 도시별 dedupe key. 예: `city-request:ES:granada` |
| `github_issue_status` | TEXT | NOT NULL | `not_required`, `created`, `linked`, `failed` |
| `created_at` | TIMESTAMPTZ | NOT NULL | 저장 시각 |

---

## visits

경로별 누적 방문 횟수. `POST /api/visits/ping` 호출 시 UPSERT로 관리됩니다.

```sql
CREATE TABLE IF NOT EXISTS visits (
    path       TEXT PRIMARY KEY,       -- 집계 경로 (예: "/dev")
    count      BIGINT NOT NULL DEFAULT 0,  -- 누적 방문 횟수
    updated_at TEXT NOT NULL           -- 마지막 방문 시각 (ISO 8601 UTC)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `path` | TEXT PK | 집계 경로 (예: `"/dev"`, `"/"`) |
| `count` | BIGINT | 누적 방문 횟수 (UPSERT로 +1) |
| `updated_at` | TEXT | 마지막 ping 시각 (ISO 8601 UTC) |

**참고:** 유저 인증 없이 집계됩니다. 경로별 독립 집계.

---

## user_city_plans

Pro 사용자가 상세 가이드 이후 확정한 활성 도시 대시보드 플랜입니다. 사용자당 하나의 active 플랜만 유지하고, 새 도시 확정 시 기존 active row는 `archived`로 전환됩니다.

```sql
CREATE TABLE IF NOT EXISTS user_city_plans (
    id               BIGSERIAL PRIMARY KEY,
    user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city_id          TEXT,
    city             TEXT NOT NULL,
    city_kr          TEXT,
    country          TEXT,
    country_id       TEXT,
    city_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    user_profile     JSONB NOT NULL DEFAULT '{}'::jsonb,
    arrived_at       TEXT,
    visa_type        TEXT NOT NULL DEFAULT '관광비자',
    visa_expires_at  TEXT,
    coworking_space  JSONB NOT NULL DEFAULT '{}'::jsonb,
    tax_profile      JSONB NOT NULL DEFAULT '{}'::jsonb,
    status           TEXT NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active', 'archived')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_city_plans_one_active
ON user_city_plans(user_id)
WHERE status = 'active';
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `city_payload` | JSONB | 추천/상세 가이드에서 넘겨받은 도시 원본 데이터 |
| `user_profile` | JSONB | 추천 시점 사용자 프로필 스냅샷 |
| `arrived_at` | TEXT | 체류 시작일 (`YYYY-MM-DD`) |
| `visa_type` | TEXT | 현재 적용 비자. 기본값은 `관광비자` |
| `visa_expires_at` | TEXT | 비자 만료일 |
| `coworking_space` | JSONB | 공유오피스 이름, 주소, 월 비용 등 사용자 입력값 |
| `tax_profile` | JSONB | 월 소득, 본국 등 세금 관리 입력값 |
| `status` | TEXT | `active` 또는 `archived` |

---

## dashboard_widget_settings

Pro 대시보드 위젯 표시 설정을 사용자별로 저장합니다. 어느 기기에서 접속해도 동일한 위젯 enable/order/settings를 사용합니다.

```sql
CREATE TABLE IF NOT EXISTS dashboard_widget_settings (
    user_id          TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    enabled_widgets  JSONB NOT NULL DEFAULT '[]'::jsonb,
    widget_order     JSONB NOT NULL DEFAULT '[]'::jsonb,
    widget_settings  JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `enabled_widgets` | JSONB | 표시할 위젯 ID 배열 |
| `widget_order` | JSONB | 표시 순서 위젯 ID 배열 |
| `widget_settings` | JSONB | 위젯별 사용자 설정값 |

---

## onboarding_drafts

비로그인 사용자가 localStorage에 저장하던 온보딩 폼/퀴즈 진행 상태를 로그인 후 서버에도 보관하는 사용자별 draft 테이블입니다. 사용자는 1개의 draft row만 가지며, 각 draft 섹션은 클라이언트가 쓰는 localStorage payload와 같은 shape로 저장합니다.

```sql
CREATE TABLE IF NOT EXISTS onboarding_drafts (
    user_id      TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    form_draft   JSONB,
    quiz_draft   JSONB,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `user_id` | TEXT PK/FK | `users.id` 참조 |
| `form_draft` | JSONB | `onboarding_form_draft_v1` localStorage payload |
| `quiz_draft` | JSONB | `onboarding_quiz_draft_v1` localStorage payload |
| `updated_at` | TIMESTAMPTZ | 마지막 저장 시각 |

운영 메모:
- `PUT /api/onboarding/draft`가 섹션별로 갱신/삭제합니다.
- 추천 결과 생성 성공 후에는 완료된 draft를 서버에서도 `null`로 정리합니다.

---

## verified_sources

검증 데이터의 출처(소스)를 관리합니다. `metric_scope`는 해당 소스가 커버하는 지표 목록입니다.

```sql
CREATE TABLE IF NOT EXISTS verified_sources (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    publisher     TEXT,
    url           TEXT NOT NULL,
    metric_scope  JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_checked  TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | TEXT PK | NOT NULL | 소스 고유 ID |
| `name` | TEXT | NOT NULL | 소스 이름 |
| `publisher` | TEXT | NULL 가능 | 발행 기관 |
| `url` | TEXT | NOT NULL | 소스 URL |
| `metric_scope` | JSONB | NOT NULL | 커버 지표 목록 (기본값: `[]`) |
| `last_checked` | TEXT | NULL 가능 | 마지막 확인 일자 (ISO 8601) |
| `updated_at` | TIMESTAMPTZ | NOT NULL | 레코드 갱신 시각 (기본값: NOW()) |

---

## verified_countries

공식 소스에서 검증된 국가별 비자 정보입니다.

```sql
CREATE TABLE IF NOT EXISTS verified_countries (
    country_id                 TEXT PRIMARY KEY,
    name                       TEXT NOT NULL,
    name_kr                    TEXT,
    visa_type                  TEXT NOT NULL,
    min_income_usd             DOUBLE PRECISION,
    stay_months                INTEGER,
    renewable                  BOOLEAN,
    visa_fee_usd               DOUBLE PRECISION,
    source_url                 TEXT,
    data_verified_date         TEXT,
    is_verified                BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data                   JSONB NOT NULL,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `country_id` | TEXT PK | NOT NULL | ISO-2 국가 코드 |
| `name` | TEXT | NOT NULL | 국가명 (영어) |
| `name_kr` | TEXT | NULL 가능 | 국가명 (한국어) |
| `visa_type` | TEXT | NOT NULL | 비자 유형 |
| `min_income_usd` | DOUBLE PRECISION | NULL 가능 | 최소 소득 요건 (USD) |
| `stay_months` | INTEGER | NULL 가능 | 허용 체류 기간 (개월) |
| `renewable` | BOOLEAN | NULL 가능 | 비자 갱신 가능 여부 |
| `visa_fee_usd` | DOUBLE PRECISION | NULL 가능 | 비자 수수료 (USD) |
| `source_url` | TEXT | NULL 가능 | 공식 출처 URL |
| `data_verified_date` | TEXT | NULL 가능 | 데이터 검증 일자 (ISO 8601) |
| `is_verified` | BOOLEAN | NOT NULL | 검증 완료 여부 (기본값: TRUE) |
| `raw_data` | JSONB | NOT NULL | 원본 데이터 전체 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | 레코드 갱신 시각 (기본값: NOW()) |

---

## verified_cities

공식 소스에서 검증된 도시별 노마드 지표입니다.

```sql
CREATE TABLE IF NOT EXISTS verified_cities (
    city_id                    TEXT PRIMARY KEY,
    city                       TEXT NOT NULL,
    city_kr                    TEXT,
    country                    TEXT,
    country_id                 TEXT NOT NULL,
    monthly_cost_usd           DOUBLE PRECISION,
    internet_mbps              DOUBLE PRECISION,
    safety_score               DOUBLE PRECISION,
    english_score              DOUBLE PRECISION,
    nomad_score                DOUBLE PRECISION,
    tax_residency_days         INTEGER,
    data_verified_date         TEXT,
    is_verified                BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data                   JSONB NOT NULL,
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `city_id` | TEXT PK | NOT NULL | 도시 고유 ID |
| `city` | TEXT | NOT NULL | 도시명 (영어) |
| `city_kr` | TEXT | NULL 가능 | 도시명 (한국어) |
| `country` | TEXT | NULL 가능 | 국가명 (영어) |
| `country_id` | TEXT | NOT NULL | ISO-2 국가 코드 (인덱스 있음) |
| `monthly_cost_usd` | DOUBLE PRECISION | NULL 가능 | 월 생활비 (USD) |
| `internet_mbps` | DOUBLE PRECISION | NULL 가능 | 인터넷 속도 (Mbps) |
| `safety_score` | DOUBLE PRECISION | NULL 가능 | 안전 점수 |
| `english_score` | DOUBLE PRECISION | NULL 가능 | 영어 통용도 점수 |
| `nomad_score` | DOUBLE PRECISION | NULL 가능 | 노마드 종합 점수 |
| `tax_residency_days` | INTEGER | NULL 가능 | 세금 거주지 기준 체류 일수 |
| `data_verified_date` | TEXT | NULL 가능 | 데이터 검증 일자 (ISO 8601) |
| `is_verified` | BOOLEAN | NOT NULL | 검증 완료 여부 (기본값: TRUE) |
| `raw_data` | JSONB | NOT NULL | 원본 데이터 전체 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | 레코드 갱신 시각 (기본값: NOW()) |

---

## verified_city_sources

도시와 소스 간 N:M 관계를 관리합니다. 도시 또는 소스 삭제 시 연결 레코드도 CASCADE 삭제됩니다.

```sql
CREATE TABLE IF NOT EXISTS verified_city_sources (
    city_id       TEXT NOT NULL REFERENCES verified_cities(city_id) ON DELETE CASCADE,
    source_id     TEXT NOT NULL REFERENCES verified_sources(id) ON DELETE CASCADE,
    linked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (city_id, source_id)
);
```

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `city_id` | TEXT FK PK | `verified_cities.city_id` 참조 |
| `source_id` | TEXT FK PK | `verified_sources.id` 참조 |
| `linked_at` | TIMESTAMPTZ | 연결 시각 (기본값: NOW()) |

---

## verification_logs

데이터 검증 작업의 전체 이력을 기록합니다.

```sql
CREATE TABLE IF NOT EXISTS verification_logs (
    id            BIGSERIAL PRIMARY KEY,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    action        TEXT NOT NULL,
    source_id     TEXT,
    verified_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes         TEXT,
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | BIGSERIAL PK | NOT NULL | 자동 증가 ID |
| `entity_type` | TEXT | NOT NULL | 대상 엔티티 타입 (예: `"city"`, `"country"`) |
| `entity_id` | TEXT | NOT NULL | 대상 엔티티 ID (복합 인덱스 있음) |
| `action` | TEXT | NOT NULL | 수행 작업 (예: `"create"`, `"update"`, `"verify"`) |
| `source_id` | TEXT | NULL 가능 | 관련 소스 ID |
| `verified_at` | TIMESTAMPTZ | NOT NULL | 작업 시각 (기본값: NOW()) |
| `notes` | TEXT | NULL 가능 | 비고 |
| `payload` | JSONB | NOT NULL | 작업 상세 데이터 (기본값: `{}`) |

---

## trips

추천 보고서를 저장한 여행. 소유자(owner)가 생성하며 동행을 초대해 공유합니다.

```sql
CREATE TABLE IF NOT EXISTS trips (
    id            TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         TEXT NOT NULL DEFAULT '',
    destination   JSONB NOT NULL,
    start_date    DATE,
    end_date      DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | TEXT PK | NOT NULL | URL-safe 토큰형 ID |
| `owner_user_id` | TEXT FK→users(id) | NOT NULL | 생성자(소유자), ON DELETE CASCADE |
| `title` | TEXT | NOT NULL | 여행 제목 (기본값 '') |
| `destination` | JSONB | NOT NULL | 추천 보고서 스냅샷 |
| `start_date` | DATE | NULL 가능 | 여행 시작일 |
| `end_date` | DATE | NULL 가능 | 여행 종료일 |
| `created_at` | TIMESTAMPTZ | NOT NULL | 생성 시각 (기본값 NOW()) |

운영 메모:
- 생성 시 owner의 `trip_members` 행이 같은 트랜잭션으로 함께 삽입됩니다(orphan 방지).

---

## trip_members

여행별 멤버와 역할. (trip_id, user_id) 복합 PK로 중복 합류를 방지합니다.

```sql
CREATE TABLE IF NOT EXISTS trip_members (
    trip_id   TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trip_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_trip_members_user ON trip_members(user_id);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `trip_id` | TEXT FK→trips(id) | NOT NULL | ON DELETE CASCADE |
| `user_id` | TEXT FK→users(id) | NOT NULL | ON DELETE CASCADE |
| `role` | TEXT | NOT NULL | `owner` 또는 `member` (기본값 'member') |
| `joined_at` | TIMESTAMPTZ | NOT NULL | 합류 시각 (기본값 NOW()) |

운영 메모:
- 합류는 멱등입니다 (`INSERT ... ON CONFLICT (trip_id, user_id) DO NOTHING`).

---

## trip_invites

여행 초대 링크 토큰. 만료(기본 14일) 전까지 재사용 가능한 멀티유즈 링크입니다.

```sql
CREATE TABLE IF NOT EXISTS trip_invites (
    token      TEXT PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trip_invites_trip ON trip_invites(trip_id);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `token` | TEXT PK | NOT NULL | URL-safe 초대 토큰 (24바이트) |
| `trip_id` | TEXT FK→trips(id) | NOT NULL | ON DELETE CASCADE |
| `created_by` | TEXT FK→users(id) | NOT NULL | 초대 발급자, ON DELETE CASCADE |
| `expires_at` | TIMESTAMPTZ | NOT NULL | 만료 시각 (발급 +14일) |
| `created_at` | TIMESTAMPTZ | NOT NULL | 발급 시각 (기본값 NOW()) |

---

## trip_plan_items

Trip 멤버들이 공동으로 작성하는 Day별 계획 항목. 추가/조회는 멤버, 수정/삭제는 작성자 또는 owner.

```sql
CREATE TABLE IF NOT EXISTS trip_plan_items (
    id         SERIAL PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day        INTEGER NOT NULL,
    time       TEXT,
    place      TEXT NOT NULL,
    category   TEXT NOT NULL,
    memo       TEXT,
    added_by   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trip_plan_items_trip ON trip_plan_items(trip_id);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | SERIAL PK | NOT NULL | 자동 증가 정수 |
| `trip_id` | TEXT FK→trips(id) | NOT NULL | ON DELETE CASCADE |
| `day` | INTEGER | NOT NULL | 여행 Day (1부터) |
| `time` | TEXT | NULL 가능 | 시간 (예: '09:00' 또는 '오전') |
| `place` | TEXT | NOT NULL | 장소/활동명 |
| `category` | TEXT | NOT NULL | 관광·식사·이동·숙소·액티비티·기타 |
| `memo` | TEXT | NULL 가능 | 메모 |
| `added_by` | TEXT FK→users(id) | NOT NULL | 작성자, ON DELETE CASCADE |
| `created_at` | TIMESTAMPTZ | NOT NULL | 생성 시각 (기본값 NOW()) |

---

## 인덱스

| 인덱스 | 대상 테이블 | 컬럼 | 용도 |
|--------|------------|------|------|
| `idx_verified_cities_country_id` | `verified_cities` | `country_id` | 국가별 도시 조회 최적화 |
| `idx_verification_logs_entity` | `verification_logs` | `(entity_type, entity_id)` | 엔티티별 로그 조회 최적화 |
| `idx_trip_members_user` | `trip_members` | `user_id` | 사용자별 참여 여행 조회 |
| `idx_trip_invites_trip` | `trip_invites` | `trip_id` | 여행별 초대 조회 |
| `idx_trip_plan_items_trip` | `trip_plan_items` | `trip_id` | 여행별 계획 항목 조회 |

---

## 관계

```
users (id)
  └── detail_guide_cache (user_id) — 1:N
  └── nomad_journey_stops (user_id) — 1:N
  └── user_city_plans (user_id) — 1:N (active는 사용자당 1개)
  └── dashboard_widget_settings (user_id) — 1:1
  └── onboarding_drafts (user_id) — 1:1
  └── trips (owner_user_id) — 1:N
  └── trip_members (user_id) — 1:N

trips (id)
  └── trip_members (trip_id) — 1:N
  └── trip_invites (trip_id) — 1:N
  └── trip_plan_items (trip_id) — 1:N

visits — 독립 테이블 (외래키 없음)

tarot_sessions — 독립 테이블 (비로그인 사용자도 발급되므로 외래키 없음, TTL 24시간)

verified_sources (id)
  └── verified_city_sources (source_id) — 1:N

verified_cities (city_id)
  └── verified_city_sources (city_id) — 1:N

verified_city_sources — verified_cities ↔ verified_sources N:M 연결 테이블

verification_logs — 독립 로그 테이블 (외래키 없음)
```

---

## 연결 정보

| 항목 | 값 |
|------|-----|
| 호스트 | Railway PostgreSQL |
| 환경변수 | `DATABASE_URL` 우선 사용; 없으면 `DATABASE_PUBLIC_URL` fallback |
| 연결 방식 | 스레드별 재사용 연결 (`utils.db.get_conn()`); 일반 요청 경로는 `connect_db()`로 연결만 생성하고 DDL을 실행하지 않음 |
| autocommit | `False` — 모든 쓰기 후 `conn.commit()` 필요 |
