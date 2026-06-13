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
