"""tests/test_travel_api.py — 여행 엔드포인트 라우터 테스트 (CI 전용; 로컬은 fastapi 부재 시 skip)"""
import json
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.travel as travel_mod


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(travel_mod.router, prefix="/api/travel")
    return TestClient(app)


def test_recommend_endpoint_returns_top_destinations():
    client = _client()
    resp = client.post("/api/travel/recommend", json={
        "travel_month": 1, "nights": 5, "budget_krw": 2000000,
        "interests": ["휴양"], "persona": "힐링 휴양러",
        "preferred_regions": ["동남아"], "top_n": 5,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["top_destinations"]) == 5
    assert "notes" in body


def test_recommend_endpoint_validates_top_n():
    client = _client()
    resp = client.post("/api/travel/recommend", json={"nights": 3, "top_n": 99})
    assert resp.status_code == 422  # top_n > 10


def test_itinerary_endpoint_returns_markdown(monkeypatch):
    good = {"city": "Bali", "city_kr": "발리", "country_id": "ID",
            "trip_title": "발리 여행", "summary": "s",
            "days": [{"day": 1, "theme": "t", "items": [
                {"time": "오전", "activity": "a", "category": "관광", "tip": "x"}]}],
            "packing_tips": [], "local_tips": []}
    monkeypatch.setattr(
        travel_mod, "build_itinerary_response",
        lambda destination, travel_profile: {"markdown": "# 발리 여행\n## Day 1", "itinerary": good},
    )
    client = _client()
    resp = client.post("/api/travel/itinerary", json={
        "destination": {"city": "Bali"}, "travel_profile": {"nights": 4},
    })
    assert resp.status_code == 200
    assert "Day 1" in resp.json()["markdown"]


def test_itinerary_endpoint_maps_unavailable_to_502(monkeypatch):
    def boom(destination, travel_profile):
        raise travel_mod.ItineraryUnavailable("ERROR: down")
    monkeypatch.setattr(travel_mod, "build_itinerary_response", boom)
    client = _client()
    resp = client.post("/api/travel/itinerary", json={
        "destination": {"city": "Bali"}, "travel_profile": {"nights": 4},
    })
    assert resp.status_code == 502
