"""tests/test_trips_service.py — Trip 서비스 테스트 (가짜 repo, DB/fastapi 불필요)"""
from datetime import datetime, timezone, timedelta
import pytest
from api import trips_service as SVC


class FakeRepo:
    """인메모리 repo. utils.db SQL 함수의 동작을 모사."""
    def __init__(self):
        self.trips = {}        # id -> trip dict
        self.members = []      # [{trip_id,user_id,role,joined_at}]
        self.invites = {}      # token -> invite dict

    def create_trip(self, owner_user_id, title, destination, start_date, end_date):
        tid = f"t{len(self.trips) + 1}"
        trip = {"id": tid, "owner_user_id": owner_user_id, "title": title,
                "destination": destination, "start_date": start_date,
                "end_date": end_date, "created_at": "2026-06-14T00:00:00Z"}
        self.trips[tid] = trip
        return trip

    def get_trip(self, trip_id):
        return self.trips.get(trip_id)

    def list_trips_for_user(self, user_id):
        ids = {m["trip_id"] for m in self.members if m["user_id"] == user_id}
        return [self.trips[i] for i in self.trips if i in ids]

    def get_member_role(self, trip_id, user_id):
        for m in self.members:
            if m["trip_id"] == trip_id and m["user_id"] == user_id:
                return m["role"]
        return None

    def get_members(self, trip_id):
        return [m for m in self.members if m["trip_id"] == trip_id]

    def add_member(self, trip_id, user_id, role):
        if self.get_member_role(trip_id, user_id) is not None:
            return  # 멱등
        self.members.append({"trip_id": trip_id, "user_id": user_id,
                             "role": role, "joined_at": "2026-06-14T00:00:00Z"})

    def create_invite(self, token, trip_id, created_by, expires_at):
        inv = {"token": token, "trip_id": trip_id, "created_by": created_by,
               "expires_at": expires_at}
        self.invites[token] = inv
        return inv

    def get_invite(self, token):
        return self.invites.get(token)


@pytest.fixture
def repo():
    return FakeRepo()


def test_create_trip_adds_owner_member(repo):
    trip = SVC.create_trip(repo, "u1", "발리 여행", {"city": "Bali"}, None, None)
    assert trip["owner_user_id"] == "u1"
    assert repo.get_member_role(trip["id"], "u1") == "owner"

def test_create_trip_returns_serialized(repo):
    trip = SVC.create_trip(repo, "u1", "발리", {"city": "Bali"}, None, None)
    assert trip["members"][0]["role"] == "owner"
    assert trip["destination"]["city"] == "Bali"

def test_list_trips_returns_user_trips(repo):
    SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    SVC.create_trip(repo, "u2", "B", {"city": "Y"}, None, None)
    mine = SVC.list_trips(repo, "u1")
    assert len(mine) == 1
    assert mine[0]["title"] == "A"

def test_get_trip_detail_member_ok(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    out = SVC.get_trip_detail(repo, trip["id"], "u1")
    assert out["id"] == trip["id"]
    assert any(m["role"] == "owner" for m in out["members"])

def test_get_trip_detail_non_member_forbidden(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    with pytest.raises(SVC.TripForbidden):
        SVC.get_trip_detail(repo, trip["id"], "stranger")

def test_get_trip_detail_missing_notfound(repo):
    with pytest.raises(SVC.TripNotFound):
        SVC.get_trip_detail(repo, "nope", "u1")


# ---------- 초대 발급/합류 ----------

def test_create_invite_member_ok(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    out = SVC.create_invite(repo, trip["id"], "u1", "https://nnai.app")
    assert out["token"]
    assert out["invite_url"].endswith(out["token"])
    assert repo.get_invite(out["token"]) is not None

def test_create_invite_non_member_forbidden(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    with pytest.raises(SVC.TripForbidden):
        SVC.create_invite(repo, trip["id"], "stranger", "https://nnai.app")

def test_create_invite_missing_trip_notfound(repo):
    with pytest.raises(SVC.TripNotFound):
        SVC.create_invite(repo, "nope", "u1", "https://nnai.app")

def test_join_trip_adds_member(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    inv = SVC.create_invite(repo, trip["id"], "u1", "https://nnai.app")
    out = SVC.join_trip(repo, inv["token"], "friend")
    assert repo.get_member_role(trip["id"], "friend") == "member"
    assert out["id"] == trip["id"]

def test_join_trip_invalid_token(repo):
    with pytest.raises(SVC.InviteInvalid):
        SVC.join_trip(repo, "bogus", "friend")

def test_join_trip_expired(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    # 만료가 과거가 되도록 now를 미래로 주입
    inv = SVC.create_invite(repo, trip["id"], "u1", "https://nnai.app", now=past)
    future = datetime(2030, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(SVC.InviteExpired):
        SVC.join_trip(repo, inv["token"], "friend", now=future)

def test_join_trip_idempotent(repo):
    trip = SVC.create_trip(repo, "u1", "A", {"city": "X"}, None, None)
    inv = SVC.create_invite(repo, trip["id"], "u1", "https://nnai.app")
    SVC.join_trip(repo, inv["token"], "friend")
    SVC.join_trip(repo, inv["token"], "friend")  # 재합류
    members = [m for m in repo.get_members(trip["id"]) if m["user_id"] == "friend"]
    assert len(members) == 1
