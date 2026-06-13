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
