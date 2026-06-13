"""tests/test_destinations.py — 여행 목적지 데이터 모델 테스트"""
import json
from pathlib import Path
import pytest
from utils.data_paths import resolve_data_path
from utils import destinations as D


# ---------- 순수 파생 함수 단위 테스트 ----------

def test_budget_tier_thresholds():
    assert D.derive_budget_tier(800) == "low"
    assert D.derive_budget_tier(1499) == "low"
    assert D.derive_budget_tier(1500) == "mid"
    assert D.derive_budget_tier(2999) == "mid"
    assert D.derive_budget_tier(3000) == "high"
    assert D.derive_budget_tier(4500) == "high"

def test_best_months_tropical():
    assert D.derive_best_months("tropical") == [11, 12, 1, 2, 3]

def test_best_months_unknown_climate_fallback():
    assert D.derive_best_months("no-such-climate") == [4, 5, 9, 10]

def test_vibe_by_climate():
    assert D.derive_vibe("tropical") == "휴양"
    assert D.derive_vibe("mediterranean") == "감성"
    assert D.derive_vibe("no-such-climate") == "도시문화"

def test_activities_non_empty():
    assert D.derive_activities("tropical")
    assert D.derive_activities("no-such-climate")

def test_kid_friendly_average():
    assert D.derive_kid_friendly(8, 6) == 7
    assert D.derive_kid_friendly(4, 4) == 4
    assert D.derive_kid_friendly(10, 10) == 10

def test_romantic_by_climate():
    assert D.derive_romantic("tropical") == 8
    assert D.derive_romantic("mediterranean") == 8
    assert D.derive_romantic("continental") == 6

def test_nightlife_by_community():
    assert D.derive_nightlife("large") == 8
    assert D.derive_nightlife("medium") == 6
    assert D.derive_nightlife("small") == 4

def test_accessibility_tiers():
    assert D.derive_accessibility("JP") == 8
    assert D.derive_accessibility("TH") == 6
    assert D.derive_accessibility("XX") == 4


# ---------- validate_destination 단위 테스트 ----------

def _minimal_dest() -> dict:
    return {
        "id": "XX", "city": "Test", "city_kr": "테스트", "country": "Testland",
        "country_id": "XX", "monthly_cost_usd": 1500, "internet_mbps": 100,
        "english_score": 7, "climate": "tropical", "safety_score": 7,
        "best_months": [11, 12, 1], "peak_season": "건기",
        "avg_flight_hours_from_icn": 6.0, "budget_tier": "mid",
        "activities": ["해변"], "vibe": "휴양", "safety": 7,
        "kid_friendly": 7, "romantic": 8, "accessibility_score": 6,
        "nightlife": 6, "must_see": [], "curated": False,
    }

def test_validate_passes_good():
    assert D.validate_destination(_minimal_dest()) == []

def test_validate_catches_missing_field():
    bad = _minimal_dest()
    del bad["vibe"]
    errs = D.validate_destination(bad)
    assert any("누락" in e for e in errs)

def test_validate_catches_bad_budget_tier():
    bad = _minimal_dest()
    bad["budget_tier"] = "cheap"
    errs = D.validate_destination(bad)
    assert any("budget_tier" in e for e in errs)

def test_validate_catches_bad_month():
    bad = _minimal_dest()
    bad["best_months"] = [13]
    errs = D.validate_destination(bad)
    assert any("best_months" in e for e in errs)

def test_validate_catches_out_of_range_score():
    bad = _minimal_dest()
    bad["nightlife"] = 11
    errs = D.validate_destination(bad)
    assert any("nightlife" in e for e in errs)

def test_validate_catches_empty_activities():
    bad = _minimal_dest()
    bad["activities"] = []
    errs = D.validate_destination(bad)
    assert any("activities" in e for e in errs)
