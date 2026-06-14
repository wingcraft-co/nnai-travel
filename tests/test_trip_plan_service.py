"""tests/test_trip_plan_service.py — 공동 플래너 서비스 테스트 (가짜 repo)"""
import pytest
from api import trip_plan_service as SVC


class FakeRepo:
    def __init__(self):
        self.trips = {"t1": {"id": "t1", "owner_user_id": "u1"}}
        self.roles = {("t1", "u1"): "owner", ("t1", "u2"): "member"}
        self.items = {}
        self._seq = 0

    def get_trip(self, trip_id):
        return self.trips.get(trip_id)

    def get_member_role(self, trip_id, user_id):
        return self.roles.get((trip_id, user_id))

    def create_plan_item(self, trip_id, day, time, place, category, added_by, memo):
        self._seq += 1
        item = {"id": self._seq, "trip_id": trip_id, "day": day, "time": time,
                "place": place, "category": category, "memo": memo,
                "added_by": added_by, "created_at": "2026-06-14T00:00:00Z"}
        self.items[self._seq] = item
        return item

    def list_plan_items(self, trip_id):
        rows = [i for i in self.items.values() if i["trip_id"] == trip_id]
        return sorted(rows, key=lambda i: (i["day"], i["time"] or "", i["id"]))

    def get_plan_item(self, item_id):
        return self.items.get(item_id)

    def update_plan_item(self, item_id, day, time, place, category, memo):
        item = self.items.get(item_id)
        if item is None:
            return None
        item.update(day=day, time=time, place=place, category=category, memo=memo)
        return item

    def delete_plan_item(self, item_id):
        self.items.pop(item_id, None)


@pytest.fixture
def repo():
    return FakeRepo()


def test_add_plan_item_member_ok(repo):
    out = SVC.add_plan_item(repo, "t1", "u2", day=1, time="09:00",
                            place="우붓", category="관광", memo="아침")
    assert out["id"] is not None
    assert out["place"] == "우붓"
    assert out["added_by"] == "u2"

def test_add_plan_item_non_member_forbidden(repo):
    with pytest.raises(SVC.TripForbidden):
        SVC.add_plan_item(repo, "t1", "stranger", day=1, time=None,
                          place="X", category="관광", memo=None)

def test_add_plan_item_missing_trip_notfound(repo):
    with pytest.raises(SVC.TripNotFound):
        SVC.add_plan_item(repo, "nope", "u1", day=1, time=None,
                          place="X", category="관광", memo=None)

def test_add_plan_item_invalid_category(repo):
    with pytest.raises(SVC.InvalidPlanItem):
        SVC.add_plan_item(repo, "t1", "u1", day=1, time=None,
                          place="X", category="아무거나", memo=None)

def test_add_plan_item_blank_place_invalid(repo):
    with pytest.raises(SVC.InvalidPlanItem):
        SVC.add_plan_item(repo, "t1", "u1", day=1, time=None,
                          place="   ", category="관광", memo=None)

def test_list_plan_items_sorted(repo):
    SVC.add_plan_item(repo, "t1", "u1", day=2, time="10:00", place="B", category="식사", memo=None)
    SVC.add_plan_item(repo, "t1", "u1", day=1, time="09:00", place="A", category="관광", memo=None)
    out = SVC.list_plan_items(repo, "t1", "u1")
    assert [i["place"] for i in out] == ["A", "B"]

def test_list_plan_items_non_member_forbidden(repo):
    with pytest.raises(SVC.TripForbidden):
        SVC.list_plan_items(repo, "t1", "stranger")
