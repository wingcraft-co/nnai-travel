"""FastAPI 백엔드 서버."""
from __future__ import annotations
from contextlib import asynccontextmanager
import logging
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pydantic import BaseModel, Field
from api.auth import router as auth_router, extract_user_id
from api.billing import router as billing_router
from api.dashboard import router as dashboard_router
from api.detail_cache import build_detail_cache_key, build_detail_quota, derive_city_id
from api.journey import router as journey_router
from api.travel import router as travel_router
from api.trips import router as trips_router
from api.onboarding import router as onboarding_router
from api.visits import router as visits_router
from utils.db import (
    claim_free_report_city,
    consume_rate_limit_token,
    ensure_database_ready,
    get_billing_entitlement,
    get_detail_guide_by_city_id,
    get_user_free_report_city_id,
    user_has_report_purchase,
    count_detail_guide_cache_entries,
    list_detail_guide_cache_entries,
    release_thread_connection_transaction,
    release_usage_reservation,
    reserve_payg_usage,
    get_detail_guide_cache,
    save_detail_guide_cache,
)
from utils.persona import persist_user_persona_type
from utils.rate_limit import (
    RateLimitPolicy,
    RequestAccessMode,
    normalize_entitlement,
    raise_rate_limit_exceeded,
    resolve_request_access_mode,
)
from utils.security_events import log_security_event

@asynccontextmanager
async def lifespan(_: FastAPI):
    """앱 시작 시 DB 스키마를 필요한 경우에만 초기화한다."""
    ensure_database_ready()
    yield


# FastAPI 앱
app = FastAPI(title="NomadNavigator API", lifespan=lifespan)

# CORS — Vercel 프론트엔드에서 백엔드 API 호출 허용
_ALLOWED_ORIGINS = [
    "https://nnai.app",
    "https://www.nnai.app",
    os.getenv("FRONTEND_URL", ""),       # Vercel 프리뷰 배포용
    "http://localhost:3000",              # 로컬 개발
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_ADS_TXT_CONTENT = "google.com, pub-8452594011595682, DIRECT, f08c47fec0942fa0"

_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>개인정보처리방침 — NomadNavigator AI</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 800px; margin: 0 auto; padding: 40px 20px;
         color: #333; line-height: 1.7; }
  h1 { font-size: 1.8rem; margin-bottom: 8px; }
  h2 { font-size: 1.2rem; margin-top: 32px; color: #111; }
  p, li { font-size: 0.95rem; color: #555; }
  a { color: #2563EB; }
  .updated { font-size: 0.85rem; color: #888; margin-bottom: 32px; }
</style>
</head>
<body>
<h1>개인정보처리방침</h1>
<p class="updated">최종 수정일: 2026년 3월 28일</p>

<p>NomadNavigator AI(이하 "서비스", nnai.app)는 이용자의 개인정보를 소중히 여기며,
관련 법령을 준수합니다.</p>

<h2>1. 수집하는 정보</h2>
<ul>
  <li>Google 로그인 시: 이름, 이메일 주소, 프로필 사진 (Google OAuth 제공 정보)</li>
  <li>서비스 이용 정보: 입력한 국적, 소득, 라이프스타일 등 추천 조건</li>
  <li>자동 수집: 접속 IP, 브라우저 종류, 방문 시각 (서버 로그)</li>
</ul>

<h2>2. 수집 목적</h2>
<ul>
  <li>AI 도시 추천 서비스 제공</li>
  <li>핀(즐겨찾기) 저장 기능 제공</li>
  <li>서비스 품질 개선 및 오류 분석</li>
</ul>

<h2>3. 제3자 제공</h2>
<p>수집한 개인정보는 원칙적으로 제3자에게 제공하지 않습니다.
단, Google AdSense를 통한 광고 게재 시 Google의 개인정보처리방침이 적용될 수 있습니다.</p>

<h2>4. 광고 및 쿠키</h2>
<p>본 서비스는 Google AdSense를 사용하며, 광고 제공을 위해 쿠키를 사용할 수 있습니다.
Google의 광고 개인정보 설정은
<a href="https://adssettings.google.com" target="_blank">adssettings.google.com</a>에서 관리하실 수 있습니다.</p>

<h2>5. 보유 및 파기</h2>
<p>회원 탈퇴 요청 시 또는 서비스 종료 시 즉시 파기합니다.
서버 로그는 최대 30일 보관 후 자동 삭제됩니다.</p>

<h2>6. 이용자 권리</h2>
<p>개인정보 열람·수정·삭제를 요청하시려면 아래 이메일로 문의해주세요.</p>

<h2>7. 문의</h2>
<p>이메일: <a href="mailto:nnai.support@gmail.com">nnai.support@gmail.com</a></p>
</body>
</html>"""


class AuthMiddleware(BaseHTTPMiddleware):
    """쿠키에서 user_id를 꺼내 request.state.user_id에 주입."""
    async def dispatch(self, request: Request, call_next):
        try:
            if request.url.path == "/ads.txt":
                return PlainTextResponse(_ADS_TXT_CONTENT)
            if request.url.path in ("/privacy", "/privacy-policy"):
                return HTMLResponse(_PRIVACY_HTML)
            request.state.user_id = extract_user_id(request)
            return await call_next(request)
        finally:
            release_thread_connection_transaction()


app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(dashboard_router)
app.include_router(journey_router, prefix="/api")
app.include_router(travel_router, prefix="/api/travel")
app.include_router(trips_router, prefix="/api/trips")
app.include_router(onboarding_router)
app.include_router(visits_router, prefix="/api")

_RATE_LIMIT_POLICY = RateLimitPolicy()


def estimate_endpoint_cost(endpoint: str) -> float:
    return {
        "recommend": 0.25,
        "detail": 0.10,
    }[endpoint]


def enforce_endpoint_rate_limit(request: Request, endpoint: str) -> tuple[str | None, dict, RequestAccessMode]:
    user_id = getattr(request.state, "user_id", None)
    entitlement = normalize_entitlement(get_billing_entitlement(user_id) if user_id else None)
    access_mode = resolve_request_access_mode(user_id, entitlement)
    subject = user_id or _RATE_LIMIT_POLICY.client_identifier(request)

    minute_limit = _RATE_LIMIT_POLICY.minute_limit(access_mode, endpoint)
    if minute_limit is not None and not consume_rate_limit_token(
        bucket_key=f"{access_mode}:{endpoint}:{subject}",
        window_name="minute",
        window_seconds=60,
        limit=minute_limit,
    ):
        log_security_event(
            "rate_limit_exceeded",
            endpoint=endpoint,
            mode=access_mode.value,
            subject=subject,
            window="minute",
        )
        raise_rate_limit_exceeded()

    burst_limit = _RATE_LIMIT_POLICY.burst_limit(access_mode, endpoint)
    if burst_limit is not None and not consume_rate_limit_token(
        bucket_key=f"{access_mode}:{endpoint}:{subject}",
        window_name="burst",
        window_seconds=1,
        limit=burst_limit,
    ):
        log_security_event(
            "rate_limit_exceeded",
            endpoint=endpoint,
            mode=access_mode.value,
            subject=subject,
            window="burst",
        )
        raise_rate_limit_exceeded()

    return user_id, entitlement, access_mode


def reserve_payg_budget_if_needed(
    user_id: str | None,
    endpoint: str,
    entitlement: dict,
    access_mode: RequestAccessMode,
) -> tuple[str | None, JSONResponse | None]:
    if not user_id or access_mode != RequestAccessMode.PRO_PAYG:
        return None, None

    request_key = uuid.uuid4().hex
    current_usage = reserve_payg_usage(
        user_id=user_id,
        endpoint=endpoint,
        request_key=request_key,
        estimated_cost_usd=estimate_endpoint_cost(endpoint),
        period_start=entitlement.get("current_period_start"),
        period_end=entitlement.get("current_period_end"),
        monthly_cap_usd=float(entitlement["payg_monthly_cap_usd"]),
    )
    if current_usage >= 0:
        log_security_event(
            "payg_cap_reached",
            endpoint=endpoint,
            subject=user_id,
            cap_usd=float(entitlement["payg_monthly_cap_usd"]),
            current_usage_usd=round(current_usage, 4),
        )
        return None, JSONResponse(
            status_code=402,
            content={
                "detail": "Monthly pay-as-you-go cap reached.",
                "cap_usd": float(entitlement["payg_monthly_cap_usd"]),
                "current_usage_usd": round(current_usage, 4),
            },
        )
    return request_key, None


# ── Frontend API Endpoints ─────────────────────────────────────


class RecommendRequest(BaseModel):
    nationality: str = Field(max_length=100)
    income_krw: int
    immigration_purpose: str = Field(max_length=500)
    lifestyle: list[str] = Field(max_length=10)
    languages: list[str] = Field(max_length=10)
    timeline: str = Field(max_length=100)
    preferred_countries: list[str] = Field(default_factory=list, max_length=10)
    preferred_language: str = Field(default="한국어", max_length=20)
    persona_type: str | None = Field(default=None, max_length=50)
    income_type: str = Field(default="", max_length=50)
    travel_type: str = Field(default="혼자 (솔로)", max_length=50)
    children_ages: list[str] | None = Field(default=None, max_length=10)
    dual_nationality: bool = False
    readiness_stage: str = Field(default="", max_length=50)
    has_spouse_income: str = Field(default="없음", max_length=20)
    spouse_income_krw: int = 0
    stay_style: str | None = Field(default=None, max_length=20)
    tax_sensitivity: str | None = Field(default=None, max_length=20)
    total_budget_krw: int | None = None
    persona_vector: dict[str, float] | None = None


class DetailRequest(BaseModel):
    parsed_data: dict
    city_index: int = 0


class LibraryGuideSaveRequest(BaseModel):
    cache_key: str = Field(max_length=128)
    markdown: str = Field(min_length=1, max_length=200_000)
    parsed_data: dict
    city_index: int = 0


@app.post("/api/recommend")
async def api_recommend(req: RecommendRequest, request: Request):
    user_id, entitlement, access_mode = enforce_endpoint_rate_limit(request, "recommend")
    reservation_key, cap_response = reserve_payg_budget_if_needed(
        user_id,
        "recommend",
        entitlement,
        access_mode,
    )
    if cap_response is not None:
        return cap_response
    if user_id:
        persist_user_persona_type(user_id, req.persona_type)

    try:
        from app import nomad_advisor
        markdown, cities, parsed = nomad_advisor(
            nationality=req.nationality,
            income_krw=req.income_krw,
            immigration_purpose=req.immigration_purpose,
            lifestyle=req.lifestyle,
            languages=req.languages,
            timeline=req.timeline,
            preferred_countries=req.preferred_countries,
            preferred_language=req.preferred_language,
            persona_type=req.persona_type,
            income_type=req.income_type,
            travel_type=req.travel_type,
            children_ages=req.children_ages,
            dual_nationality=req.dual_nationality,
            readiness_stage=req.readiness_stage,
            has_spouse_income=req.has_spouse_income,
            spouse_income_krw=req.spouse_income_krw,
            stay_style=req.stay_style,
            tax_sensitivity=req.tax_sensitivity,
            total_budget_krw=req.total_budget_krw,
            persona_vector=req.persona_vector,
        )
        # 타로 세션: 5장 저장, 상세 데이터 미포함 응답
        from api.tarot_session import create_session
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info("[api/recommend] cities=%d before session create", len(cities))
        session_id = create_session(cities)

        return {
            "session_id": session_id,
            "card_count": len(cities),
            "parsed": parsed,
        }
    except Exception:
        if reservation_key:
            release_usage_reservation(reservation_key)
        raise


class RevealRequest(BaseModel):
    session_id: str
    selected_indices: list[int]


@app.post("/api/reveal")
async def api_reveal(req: RevealRequest):
    from api.tarot_session import reveal_cards
    try:
        revealed = reveal_cards(req.session_id, req.selected_indices)
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"error": str(e)})
    return {"revealed_cities": revealed}


@app.post("/api/detail")
async def api_detail(req: DetailRequest, request: Request):
    """단건 결제 모델 (2026-05-25 변경):

    - 비로그인: 401
    - 결제 완료 도시 (`is_free=false`) → 풀콘텐츠 markdown + `is_free=false`
    - 무료 부여 도시 (`is_free=true`) → 동일 markdown + `is_free=true` (프론트가 워터마크+블러)
    - 무료 보고서 미사용 + 첫 요청 → 이 도시를 무료로 자동 부여 + LLM 호출 (is_free=true)
    - 무료 보고서 사용 완료(다른 도시) + 미결제 → 402 Payment Required
    """
    user_id, entitlement, access_mode = enforce_endpoint_rate_limit(request, "detail")
    cache_key = build_detail_cache_key(req.parsed_data, req.city_index)
    city_id = derive_city_id(req.parsed_data, req.city_index)

    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Login required to receive a guide."},
        )

    # 1. city_id별 기존 보고서 조회 (결제분 우선)
    if city_id:
        existing = get_detail_guide_by_city_id(user_id, city_id)
        if existing:
            return {
                "markdown": existing["markdown"],
                "cached": True,
                "cache_key": existing["cache_key"],
                "city_id": existing["city_id"],
                "is_free": existing["is_free"],
            }

    # 2. cache_key 기반 fallback (city_id 없는 과거 데이터 호환)
    cached = get_detail_guide_cache(user_id, cache_key)
    if cached:
        return {
            "markdown": cached["markdown"],
            "cached": True,
            "cache_key": cache_key,
            "city_id": city_id,
            "is_free": cached.get("is_free", False),
        }

    # 3. 무료 보고서 1회 부여 가능한가?
    is_free = False
    if city_id:
        has_paid_report = bool(city_id and user_has_report_purchase(user_id, city_id))
        existing_free_city = get_user_free_report_city_id(user_id)
        if has_paid_report:
            is_free = False
        elif existing_free_city is None:
            # 무료 미사용 → 이 도시로 부여
            claimed = claim_free_report_city(user_id, city_id)
            if claimed:
                is_free = True
        elif existing_free_city == city_id:
            # 무료 도시와 동일 (보고서가 아직 생성 안 됐을 경우)
            is_free = True
        else:
            # 무료 도시와 다른 도시 + 미결제 → 결제 필요
            return JSONResponse(
                status_code=402,
                content={
                    "detail": "Payment required for this city report.",
                    "city_id": city_id,
                    "free_used_for": existing_free_city,
                    "price_usd": 2.99,
                    "list_price_usd": 4.99,
                },
            )
    else:
        # city_id 도출 실패 — 보수적으로 결제 요구
        return JSONResponse(
            status_code=400,
            content={"detail": "city_id could not be derived from parsed_data."},
        )

    reservation_key, cap_response = reserve_payg_budget_if_needed(
        user_id,
        "detail",
        entitlement,
        access_mode,
    )
    if cap_response is not None:
        return cap_response
    try:
        from app import show_city_detail_with_nationality, LLMUnavailableError
        try:
            markdown = show_city_detail_with_nationality(
                parsed_data=req.parsed_data,
                city_index=req.city_index,
            )
        except LLMUnavailableError as llm_err:
            if reservation_key:
                release_usage_reservation(reservation_key)
            logger.warning(f"[api_detail] LLM unavailable after retries: {llm_err!s}")
            raise HTTPException(
                status_code=502,
                detail="LLM 서비스가 일시적으로 불안정합니다. 잠시 후 다시 시도해주세요.",
            )
        save_detail_guide_cache(
            user_id=user_id,
            cache_key=cache_key,
            markdown=markdown,
            parsed_data=req.parsed_data,
            city_index=req.city_index,
            city_id=city_id,
            is_free=is_free,
        )
        return {
            "markdown": markdown,
            "cached": False,
            "cache_key": cache_key,
            "city_id": city_id,
            "is_free": is_free,
        }
    except HTTPException:
        raise
    except Exception:
        if reservation_key:
            release_usage_reservation(reservation_key)
        raise


@app.get("/api/library/guides")
async def api_library_guides(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")
    return {"guides": list_detail_guide_cache_entries(user_id)}


@app.post("/api/library/guides")
async def api_save_library_guide(req: LibraryGuideSaveRequest, request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")
    guide = save_detail_guide_cache(
        user_id=user_id,
        cache_key=req.cache_key,
        markdown=req.markdown,
        parsed_data=req.parsed_data,
        city_index=req.city_index,
    )
    return {"guide": guide}


# 직접 실행 시 uvicorn
if __name__ == "__main__":
    import uvicorn
    _is_hf = bool(os.getenv("SPACE_ID"))
    _is_railway = bool(os.getenv("RAILWAY_ENVIRONMENT"))
    _is_cloud = _is_hf or _is_railway
    uvicorn.run(
        "server:app",
        host="0.0.0.0" if _is_cloud else "127.0.0.1",
        port=int(os.getenv("PORT", 7860)),
        reload=not _is_cloud,
    )
