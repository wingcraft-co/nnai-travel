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
