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
