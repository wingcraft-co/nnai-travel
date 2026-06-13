"""tests/test_travel_budget.py — 여행 비용 추정 단위 테스트"""
from utils import travel_budget as B


def _dest(cost=1200, hours=7.0):
    return {"monthly_cost_usd": cost, "avg_flight_hours_from_icn": hours}


def test_flight_usd_increases_with_hours():
    assert B.estimate_flight_usd(1.5) < B.estimate_flight_usd(7.0) < B.estimate_flight_usd(14.0)

def test_flight_usd_positive():
    assert B.estimate_flight_usd(0.0) > 0

def test_daily_usd_from_monthly():
    # 1500/30 = 50, *1.4 관광보정 = 70.0
    assert B.estimate_daily_usd(1500) == 70.0

def test_trip_cost_krw_known_value():
    # flight = round(120 + 7.0*75) = 645, daily = 1200/30*1.4 = 56.0
    # total_usd = 645 + 56*4 = 869, *1400 = 1216600
    cost = B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=4)
    assert cost == 1216600

def test_trip_cost_krw_zero_nights():
    # nights=0 → 항공료만
    cost = B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=0)
    assert cost == round(B.estimate_flight_usd(7.0) * B.USD_KRW_FALLBACK)

def test_trip_cost_krw_clamps_negative_nights():
    assert B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=-3) == B.estimate_trip_cost_krw(_dest(1200, 7.0), nights=0)

def test_budget_fit_no_budget_is_neutral():
    assert B.budget_fit_score(999999, 0) == 6.0

def test_budget_fit_thresholds():
    # ratio = est/budget
    assert B.budget_fit_score(50, 100) == 8.0    # 0.5 → 저렴
    assert B.budget_fit_score(80, 100) == 10.0   # 0.8 → 최적
    assert B.budget_fit_score(100, 100) == 10.0  # 1.0 경계
    assert B.budget_fit_score(110, 100) == 6.0   # 1.1 약간 초과
    assert B.budget_fit_score(140, 100) == 3.0   # 1.4 초과
    assert B.budget_fit_score(200, 100) == 1.0   # 2.0 대폭 초과
