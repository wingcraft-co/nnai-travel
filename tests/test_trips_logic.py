"""tests/test_trips_logic.py — Trip 순수 헬퍼 테스트 (DB/fastapi 불필요)"""
from datetime import datetime, timezone, timedelta
from api import trips_logic as L


def test_generate_trip_id_unique_and_urlsafe():
    a, b = L.generate_trip_id(), L.generate_trip_id()
    assert a != b
    assert len(a) >= 16
    assert all(c.isalnum() or c in "-_" for c in a)

def test_generate_invite_token_unique():
    a, b = L.generate_invite_token(), L.generate_invite_token()
    assert a != b
    assert len(a) >= 24

def test_invite_expiry_default_14_days():
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    exp = L.invite_expiry(now)
    assert exp == now + timedelta(days=14)

def test_invite_expiry_custom_days():
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    assert L.invite_expiry(now, days=3) == now + timedelta(days=3)

def test_is_invite_expired():
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    assert L.is_invite_expired(now - timedelta(seconds=1), now) is True
    assert L.is_invite_expired(now + timedelta(days=1), now) is False
    assert L.is_invite_expired(now, now) is True  # 경계 = 만료

def test_build_invite_url():
    url = L.build_invite_url("https://nnai.app", "abc123")
    assert url == "https://nnai.app/trips/join?token=abc123"

def test_build_invite_url_strips_trailing_slash():
    assert L.build_invite_url("https://nnai.app/", "t") == "https://nnai.app/trips/join?token=t"

def test_is_member_role():
    assert L.is_member_role("owner") is True
    assert L.is_member_role("member") is True
    assert L.is_member_role(None) is False
    assert L.is_member_role("") is False

def test_serialize_trip_shapes_output():
    trip = {"id": "t1", "owner_user_id": "u1", "title": "발리", "destination": {"city": "Bali"},
            "start_date": "2026-07-01", "end_date": "2026-07-05", "created_at": "2026-06-14T00:00:00Z"}
    members = [{"user_id": "u1", "role": "owner", "joined_at": "2026-06-14T00:00:00Z"}]
    out = L.serialize_trip(trip, members)
    assert out["id"] == "t1"
    assert out["title"] == "발리"
    assert out["destination"]["city"] == "Bali"
    assert out["members"] == members
    assert "owner_user_id" in out
