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
