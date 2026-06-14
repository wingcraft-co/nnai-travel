"""tests/test_trips_api.py — Trip 라우터 테스트 (CI 전용; 로컬 fastapi 부재 시 skip).

라우터의 auth 게이팅·예외 매핑을 가짜 service로 검증한다(실 DB 불필요).
"""
import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import api.trips as trips_mod
from api import trips_service as SVC


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


def test_create_trip_requires_login(monkeypatch):
    resp = _client_anon().post("/api/trips", json={"title": "A", "destination": {"city": "X"}})
    assert resp.status_code == 401


def test_create_trip_ok(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    monkeypatch.setattr(SVC, "create_trip",
                        lambda repo, uid, title, dest, sd, ed: {"id": "t1", "title": title,
                                                                "members": [], "destination": dest})
    resp = _client().post("/api/trips", json={"title": "발리", "destination": {"city": "Bali"}})
    assert resp.status_code == 200
    assert resp.json()["id"] == "t1"


def test_get_trip_forbidden_maps_403(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, trip_id, uid):
        raise SVC.TripForbidden(trip_id)
    monkeypatch.setattr(SVC, "get_trip_detail", boom)
    resp = _client().get("/api/trips/t1")
    assert resp.status_code == 403


def test_get_trip_notfound_maps_404(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, trip_id, uid):
        raise SVC.TripNotFound(trip_id)
    monkeypatch.setattr(SVC, "get_trip_detail", boom)
    resp = _client().get("/api/trips/t1")
    assert resp.status_code == 404


def test_join_invalid_token_maps_400(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, token, uid, now=None):
        raise SVC.InviteInvalid(token)
    monkeypatch.setattr(SVC, "join_trip", boom)
    resp = _client().post("/api/trips/join", json={"token": "bogus"})
    assert resp.status_code == 400


def test_join_expired_maps_410(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, token, uid, now=None):
        raise SVC.InviteExpired(token)
    monkeypatch.setattr(SVC, "join_trip", boom)
    resp = _client().post("/api/trips/join", json={"token": "old"})
    assert resp.status_code == 410


def test_list_trips_requires_login():
    resp = _client_anon().get("/api/trips")
    assert resp.status_code == 401

def test_create_invite_requires_login():
    resp = _client_anon().post("/api/trips/t1/invites")
    assert resp.status_code == 401

def test_join_requires_login():
    resp = _client_anon().post("/api/trips/join", json={"token": "x"})
    assert resp.status_code == 401
