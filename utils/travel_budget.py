"""utils/travel_budget.py — 여행 비용 추정 (순수 함수, 결정론적).

환율은 네트워크 없이 결정론적 테스트를 위해 고정 fallback 상수를 사용한다.
실제 환율 반영이 필요하면 호출부에서 usd_krw 인자로 주입한다.
"""
from __future__ import annotations

USD_KRW_FALLBACK = 1400


def estimate_flight_usd(flight_hours: float) -> int:
    """ICN 출발 왕복 항공료 근사(USD). 비행시간 기반 선형 추정."""
    return round(120 + flight_hours * 75)


def estimate_daily_usd(monthly_cost_usd: int) -> float:
    """월 생활비 → 1일 여행 경비 근사. 관광 보정 1.4배."""
    return monthly_cost_usd / 30.0 * 1.4


def estimate_trip_cost_krw(
    dest: dict, nights: int, headcount: int = 1,
    usd_krw: float = USD_KRW_FALLBACK,
) -> int:
    """1인 기준 총 여행비(KRW) 추정.

    예산은 spec상 '1인 총액'이므로 headcount는 1인 단가에 영향을 주지 않는다
    (동행 인원은 동행 블록에서만 활용). 시그니처는 호출 호환성을 위해 유지한다.
    """
    nights = max(0, nights)
    flight = estimate_flight_usd(dest["avg_flight_hours_from_icn"])
    daily = estimate_daily_usd(dest["monthly_cost_usd"])
    total_usd = flight + daily * nights
    return round(total_usd * usd_krw)


def budget_fit_score(est_krw: int, budget_krw: int) -> float:
    """예산 적합도 0~10. 예산 내가 최적, 초과 시 단계적 감점. 예산 미입력=중립."""
    if budget_krw <= 0:
        return 6.0
    ratio = est_krw / budget_krw
    if ratio <= 0.6:
        return 8.0
    if ratio <= 1.0:
        return 10.0
    if ratio <= 1.2:
        return 6.0
    if ratio <= 1.5:
        return 3.0
    return 1.0
