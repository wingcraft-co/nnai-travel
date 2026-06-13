"""utils/destinations.py — 여행 목적지 데이터 스키마, 파생 함수, 로더/검증."""
import json
from utils.data_paths import resolve_data_path

BUDGET_TIERS = ("low", "mid", "high")

_CLIMATE_BEST_MONTHS = {
    "tropical": [11, 12, 1, 2, 3],
    "subtropical": [3, 4, 5, 10, 11],
    "mediterranean": [5, 6, 9, 10],
    "continental": [5, 6, 9],
    "temperate": [4, 5, 9, 10],
    "maritime": [6, 7, 8, 9],
    "highland": [4, 5, 9, 10, 11],
    "desert": [11, 12, 1, 2, 3],
    "semi-arid": [3, 4, 5, 10, 11],
}
_CLIMATE_VIBE = {
    "tropical": "휴양", "subtropical": "휴양", "mediterranean": "감성",
    "continental": "도시문화", "temperate": "도시문화", "maritime": "도시문화",
    "highland": "자연", "desert": "이국", "semi-arid": "자연",
}
_CLIMATE_ACTIVITIES = {
    "tropical": ["해변", "스노클링", "리조트", "카페"],
    "subtropical": ["해변", "온천", "카페", "도보관광"],
    "mediterranean": ["해변", "미식", "도보관광", "와인"],
    "continental": ["도시관광", "미술관", "미식", "쇼핑"],
    "temperate": ["도시관광", "미술관", "미식", "쇼핑"],
    "maritime": ["도시관광", "미술관", "미식", "쇼핑"],
    "highland": ["트레킹", "자연", "전망"],
    "desert": ["사막투어", "럭셔리", "쇼핑"],
    "semi-arid": ["트레킹", "자연", "전망"],
}
_CLIMATE_PEAK = {
    "tropical": "11~3월 건기", "subtropical": "봄·가을", "mediterranean": "5~10월 성수기",
    "continental": "여름 성수기", "temperate": "봄·가을", "maritime": "여름",
    "highland": "건기", "desert": "겨울", "semi-arid": "봄·가을",
}
_NIGHTLIFE_BY_COMMUNITY = {"large": 8, "medium": 6, "small": 4}
_ROMANTIC_CLIMATES = {"tropical", "subtropical", "mediterranean"}

_DEVELOPED_COUNTRIES = {
    "PT", "ES", "DE", "EE", "GR", "NL", "AT", "CZ", "HU", "PL",
    "IT", "HR", "JP", "TW", "AE", "QA", "CY", "US",
}
_MID_COUNTRIES = {
    "TH", "MY", "VN", "ID", "PH", "GE", "TR", "RS", "MK", "ME",
    "MA", "CR", "MX", "AR", "UY", "PE", "CO", "SI", "BG", "RO", "AL",
}


def derive_budget_tier(monthly_cost_usd: int) -> str:
    if monthly_cost_usd < 1500:
        return "low"
    if monthly_cost_usd < 3000:
        return "mid"
    return "high"


def derive_best_months(climate: str) -> list[int]:
    return list(_CLIMATE_BEST_MONTHS.get(climate, [4, 5, 9, 10]))


def derive_vibe(climate: str) -> str:
    return _CLIMATE_VIBE.get(climate, "도시문화")


def derive_activities(climate: str) -> list[str]:
    return list(_CLIMATE_ACTIVITIES.get(climate, ["도시관광", "미식"]))


def derive_peak_season(climate: str) -> str:
    return _CLIMATE_PEAK.get(climate, "봄·가을")


def _clamp(value: int, low: int = 1, high: int = 10) -> int:
    return max(low, min(high, value))


def derive_kid_friendly(safety_score: int, english_score: int) -> int:
    return _clamp(round((safety_score + english_score) / 2))


def derive_romantic(climate: str) -> int:
    return 8 if climate in _ROMANTIC_CLIMATES else 6


def derive_nightlife(community_size: str) -> int:
    return _NIGHTLIFE_BY_COMMUNITY.get(community_size, 5)


def derive_accessibility(country_id: str) -> int:
    if country_id in _DEVELOPED_COUNTRIES:
        return 8
    if country_id in _MID_COUNTRIES:
        return 6
    return 4
