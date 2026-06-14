"""tests/test_trip_plan_api.py — 공동 플래너 라우터 테스트 (CI 전용; 로컬 skip)"""
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import api.trips as trips_mod
from api import trip_plan_service as PSVC


def _client(user_id="u1"):
    app = FastAPI()

    @app.middleware("http")
    async def _inject_user(request: Request, call_next):
        request.state.user_id = user_id
        return await call_next(request)

    app.include_router(trips_mod.router, prefix="/api/trips")
    return TestClient(app)


def _client_anon():
    app = FastAPI()
    app.include_router(trips_mod.router, prefix="/api/trips")
    return TestClient(app)


def test_add_plan_item_requires_login():
    resp = _client_anon().post("/api/trips/t1/plan-items",
                               json={"day": 1, "place": "우붓", "category": "관광"})
    assert resp.status_code == 401


def test_add_plan_item_ok(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    monkeypatch.setattr(PSVC, "add_plan_item",
                        lambda repo, tid, uid, day, time, place, category, memo: {
                            "id": 1, "trip_id": tid, "place": place, "category": category})
    resp = _client().post("/api/trips/t1/plan-items",
                          json={"day": 1, "time": "09:00", "place": "우붓",
                                "category": "관광", "memo": "아침"})
    assert resp.status_code == 200
    assert resp.json()["id"] == 1


def test_add_plan_item_invalid_category_maps_400(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, tid, uid, day, time, place, category, memo):
        raise PSVC.InvalidPlanItem("bad")
    monkeypatch.setattr(PSVC, "add_plan_item", boom)
    resp = _client().post("/api/trips/t1/plan-items",
                          json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 400


def test_add_plan_item_forbidden_maps_403(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, tid, uid, day, time, place, category, memo):
        raise PSVC.TripForbidden(tid)
    monkeypatch.setattr(PSVC, "add_plan_item", boom)
    resp = _client().post("/api/trips/t1/plan-items",
                          json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 403


def test_list_plan_items_ok(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    monkeypatch.setattr(PSVC, "list_plan_items",
                        lambda repo, tid, uid: [{"id": 1, "place": "우붓"}])
    resp = _client().get("/api/trips/t1/plan-items")
    assert resp.status_code == 200
    assert resp.json()["plan_items"][0]["place"] == "우붓"


def test_update_plan_item_notfound_maps_404(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, tid, item_id, uid, **kw):
        raise PSVC.PlanItemNotFound(item_id)
    monkeypatch.setattr(PSVC, "update_plan_item", boom)
    resp = _client().put("/api/trips/t1/plan-items/9",
                         json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 404


def test_update_plan_item_forbidden_maps_403(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, tid, item_id, uid, **kw):
        raise PSVC.PlanItemForbidden(item_id)
    monkeypatch.setattr(PSVC, "update_plan_item", boom)
    resp = _client().put("/api/trips/t1/plan-items/9",
                         json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 403


def test_delete_plan_item_ok(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    monkeypatch.setattr(PSVC, "delete_plan_item", lambda repo, tid, item_id, uid: None)
    resp = _client().delete("/api/trips/t1/plan-items/9")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


def test_delete_plan_item_requires_login():
    resp = _client_anon().delete("/api/trips/t1/plan-items/9")
    assert resp.status_code == 401


def test_list_plan_items_requires_login():
    resp = _client_anon().get("/api/trips/t1/plan-items")
    assert resp.status_code == 401

def test_update_plan_item_requires_login():
    resp = _client_anon().put("/api/trips/t1/plan-items/9",
                              json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 401
