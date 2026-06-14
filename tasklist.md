# Task List

프로젝트 작업 이력을 날짜별로 짧게 남기는 공유 로그입니다.
누가 작업하든 아래 형식처럼 날짜마다 요약 2줄 정도로 남깁니다.

## 작성 형식

```markdown
## YYYY-MM-DD
- 진행한 주요 작업을 한 문장으로 작성
- 이어서 필요한 맥락이나 후속 작업을 한 문장으로 작성
```

## 작업 로그

## 2026-05-21
- `tasklist.md`를 추가하고 날짜별 작업 요약 로그 형식을 정의함.
- `CLAUDE.md`에도 작업자 이름 없이 날짜별 요약 2줄 정도를 남기는 규칙을 추가함.

## 2026-05-22
- 온보딩 페르소나 결과에서 `거침없는 나그네`, `어디서든 현지인`, `용감한 개척자`는 픽셀 캐릭터 밑줄을 숨김.
- `/library` 노마드 카드 컬렉션 MVP를 추가하고, 비로그인 임시 카드는 10초마다 30%까지 흐려지도록 구현함.

## 2026-05-23
- 가이드 페이지에 locale 기반 LLM 응답 언어 강제, 마크다운 URL 자동 링크화, 이미지 우클릭 방지, 로딩 UI 개선 등 다수 UX 개선 적용.
- 무료 사용자 맞춤보고서 이미지에 우클릭/드래그/iOS 롱프레스 저장 차단 추가 (`pointerEvents`, `WebkitTouchCallout` 등), `feature-flags.ts` 신규 추가.
- 타로 결과 lightbox의 "Google로 계속하기" 버튼 OAuth 버그 수정: `return_to`를 현재 result 페이지 URL로 변경하고, `pending_login_city_id`를 sessionStorage에 저장 후 OAuth 복귀 시 lightbox 자동 복원.
- `TarotDeck.tsx`에 OAuth 복귀 후 lightbox 재오픈 useEffect 추가 — 로그인 완료 후 선택했던 도시 카드로 자동으로 돌아옴.
- 유료 Step 2 보고서 강화 제안서(`cowork/marketing/paid-report-enhancement.md`) 작성 — 설문 입력이 보고서 섹션에 1:1로 호명되도록 10개 카테고리(A~J) 제안, 무료/유료 분기 표·출력 스키마 확장안·구현 우선순위 포함.

## 2026-05-24
- 보관함 카드 REPORT/CARD/LOCKED 카테고리화 + 헤더에 카운트 표시, 한글 도시명 음절 중간 줄바꿈 방지(`break-keep`).
- 가이드 구매 후 보관함의 CARD가 REPORT로 승격되도록 `mergeLibraryCards` 수정, 회귀 테스트 추가.
- 보관함→guide 진입 시 `?from=library` 분기 처리(뒤로가기 라벨/목적지). 라이브러리에서 진입할 때 세션 revealedCities[0]로 잘못 fallback되던 버그 수정.
- 국기 이모지 lookup 테이블 3종(`TarotDeck`, `TarotReading`, `TarotCard`) 통합 → ISO-2 Regional Indicator 기반 `@/lib/country-flag` 유틸로 일원화 (PY 등 누락 국가가 🌍로 표시되던 문제 해결).
- DB 점검 및 오래된 자료 정리: `scripts/migrate_sqlite_to_pg.py`, `scripts/drop_mobile_tables.sql`, `tests/test_pdf_generator.py`, `IMPLEMENTATION_STATUS.md` 삭제. utils/db.py ↔ db-schema.md 동기화 상태 확인.
- 타로 세션 PostgreSQL 마이그레이션: `tarot_sessions` 테이블 신설 (TTL 24시간, lazy cleanup, `SELECT FOR UPDATE` 동시성 처리). `api/tarot_session.py`의 in-memory `_sessions` 딕셔너리 제거 → Railway 재배포 시 세션 유실 문제 해결. CI에 `test_tarot_session.py` 등록.
- 프론트엔드 의존성 취약점 14건 해결: `next` 16.2.4 → 16.2.6, `hono` overrides 4.12.22, `@hono/node-server` 2.0.4, `postcss` override ^8.5.10 추가. `npm audit fix` + 수동 버전 업으로 0건 달성.

## 2026-05-25
- 유료 보고서 강화 Phase 1 spec(`cowork/marketing/paid-report-phase1-spec.md`) 정리: A·I·G·H 4개 카테고리(Personalized Summary·Resource Pack·Pre-Departure Timeline·Plan B) 구현 우선순위 결정.
- Pricing 단건 결제 전환 spec(`cowork/marketing/pricing-migration-spec.md`) 신설: free/pro 폐지, 보고서당 정가 $4.99 / 런칭 할인 $2.99 단건 결제, Polar 단일 product + city_id metadata.
- 무료 사용자 정책: 평생 1개 도시 보고서 풀콘텐츠 제공 (LLM 분기 없음 — 응답 `is_free` 플래그로 프론트 분기). 무료 = **앞 3섹션 명확 + 뒷부분 블러(`blur-sm`) + 대각선 워터마크 + 다운로드 잠금**. 결제 시 모두 해제. DB: `users.free_report_city_id`, `detail_guide_cache.is_free`/`city_id` 컬럼 신설.
- P1 백엔드 단건 결제 모델 구현 완료: `utils/db.py` 헬퍼(`get_user_free_report_city_id`, `claim_free_report_city`, `get_detail_guide_by_city_id`, `list_user_owned_city_ids`, `mark_report_purchased`) 추가, `api/detail_cache.py`에 `derive_city_id` 추가, `/api/detail` 가드를 quota 기반 → city_id 단건 모델로 교체 (401/402/200 + is_free 응답), `/auth/me` 응답에 `free_report_city_id`·`library` 추가. `cowork/backend/db-schema.md`·`api-reference.md` 동기화. 회귀 385 PASS.
- 결제 API를 provider-neutral 구조로 분리: 기본 `BILLING_PROVIDER=portone`, 글로벌 전환용 `polar` adapter 유지, `/api/billing/*` 경로는 유지.
- 가이드 페이지 결제 요청에 `city_id`를 포함하고, Polar 직링크는 provider가 `polar`일 때만 사용하도록 BFF/프론트 우회 조건을 제한함.
- PortOne V2 브라우저 SDK를 추가하고 `/api/billing/complete` 서버 검증 플로우를 구현함: `paymentId` 조회 → `PAID`/금액/`customData` 검증 → `report_purchases` 구매 기록 저장.
- 프론트 결제 버튼은 PortOne SDK 결제창 호출 후 구매 확정 페이지로 복귀하며, 모바일 리디렉션 복귀 시에도 가이드 페이지가 `paymentId`를 재검증하도록 처리함.

## 2026-06-13
- 여행지 추천+협업 플래너 전환 설계 spec(`docs/specs/2026-06-13-travel-pivot-design.md`)과 Phase 1 데이터 모델 구현 계획(`docs/plans/2026-06-13-phase1-destinations-data-model.md`) 작성. 기존 nnai 코드/DB와 완전 격리(별도 repo·Railway `nnai-travel-prd`) 원칙 명시.
- Phase 1 완료: `utils/destinations.py`에 결정론적 파생 함수 + editorial 오버라이드 + `validate_destination`/로더 구현, `scripts/build_destinations.py`로 `city_scores.json`+큐레이션 CSV → `destinations.json`(52개, 큐레이션 10개) 빌드. 프론트 복사본 동기화, 통합 포함 테스트 22개 통과 + CI 등록.
- Phase 2 완료: `travel_recommender.py`(시즌·예산·관심사/성향·안전품질·동행 5블록 가중합 + 권역 소프트폴백 + 접근성 하드필터) + `utils/travel_budget.py`(결정론적 경비/예산 추정) 신설. 기존 이민용 recommender.py·visa_db는 미변경.
- 여행 추천엔진 테스트 43개(경비 8 + 엔진 35) 통과 + CI 등록. destinations.json 기반 결정론적 랭킹, 국가 중복 제거 없음.
- Phase 3 완료: 여행 일정(N박M일) LLM 플래너 신설 — `prompts/itinerary.py`(프로필→프롬프트 헬퍼+빌더), `prompts/itinerary_system.py`(ko/en 스키마), `api/itinerary_parser.py`(robust 파싱 + Day별 마크다운 렌더). 기존 이민용 builder.py·parser.py 미변경.
- 일정 플래너 테스트 30개(프롬프트 19 + 파서/렌더 11) 통과 + CI 등록. LLM 호출/엔드포인트 배선은 Phase 4 범위.
- Phase 4(백엔드 배선) 완료: `api/travel_service.py`(순수 도메인 로직, LLM 주입 가능) + `api/travel.py`(FastAPI 라우터) 신설, `server.py`에 `/api/travel/recommend`·`/api/travel/itinerary` 연결. 기존 이민 엔드포인트 미변경. `cowork/backend/api-reference.md` 동기화.
- 서비스 테스트 7개(로컬, 결정론적) + 라우터 테스트 4개(CI 전용, fastapi importorskip) + CI 등록. 인증/결제/rate-limit은 추후 별도 협의.

## 2026-06-14
- Phase 5(Trip & 동행 초대) 완료: `trips`/`trip_members`/`trip_invites` 테이블(init_db 멱등 DDL, 스키마 가드 등록) + SQL repo, `api/trips_logic.py`(토큰·만료·권한 순수 헬퍼)·`api/trips_service.py`(orchestration, 주입 repo, 도메인 예외)·`api/trips.py`(FastAPI 라우터, /api/trips 5개 엔드포인트) 신설, `server.py` 배선. `db-schema.md`·`api-reference.md` 동기화.
- 순수 로직/서비스 테스트 23개(로컬 결정론적, 가짜 repo) + 라우터 테스트 9개(CI 전용, fastapi importorskip) + CI 등록. 초대는 만료(14일) 기반 멀티유즈 링크, 합류 멱등, Trip 생성은 owner 멤버와 단일 트랜잭션. SQL/실DB는 Railway 배포 시 검증.
