# Phase 6 — 공동 여행 플래너 (trip_plan_items) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trip 멤버들이 Day별 여행 계획 항목(장소·시간·카테고리·메모)을 공동으로 추가/조회/수정/삭제하는 협업 플래너 백엔드를 구축한다.

**Architecture:** Phase 5와 동일한 3계층(pure logic / injected-repo service / SQL repo) + 기존 `api/trips.py` 라우터에 plan-item 엔드포인트를 추가한다. 권한은 Phase 5의 Trip 멤버십을 재사용한다(추가/조회=멤버, 수정/삭제=작성자 또는 owner). DB 의존 코드는 배포 검증, 로직/서비스는 로컬 결정론적 테스트.

**Tech Stack:** FastAPI, psycopg2(PostgreSQL), Pydantic, pytest. 테스트는 `SKIP_EXTERNAL_INIT=1 python3 -m pytest`.

---

## 격리/원칙 (필수)

- 기존 테이블/이민 경로 변경 금지. `init_db()`에 신규 `trip_plan_items` 멱등 DDL만 추가.
- 기존 `api/trips.py`는 plan-item 엔드포인트 **추가만**(기존 5개 엔드포인트 미변경). `_DbRepo`에 plan-item 메서드 추가.
- push는 항상 `develop`. `main` 금지.
- **CLAUDE.md 규칙**: 테이블 추가 → `cowork/backend/db-schema.md`, 엔드포인트 추가 → `cowork/backend/api-reference.md` 동기화(Task 6).
- 새 테스트 파일은 `.github/workflows/main-tests.yml` 등록(Task 6). 작업 로그 `tasklist.md`(Task 6).
- 환경: 로컬 `fastapi`/`psycopg2` 부재(CI엔 있으나 Postgres 없음). 로직/서비스만 로컬+CI 자동검증, SQL/라우터는 배포 검증 + 라우터는 CI에서 가짜 service로 검증.

## 데이터 모델 (init_db DDL)

```sql
CREATE TABLE IF NOT EXISTS trip_plan_items (
    id         SERIAL PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day        INTEGER NOT NULL,
    time       TEXT,
    place      TEXT NOT NULL,
    category   TEXT NOT NULL,
    memo       TEXT,
    added_by   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trip_plan_items_trip ON trip_plan_items(trip_id);
```

- `id`는 SERIAL(정수, DB 자동 부여). `category` 허용값: `관광`, `식사`, `이동`, `숙소`, `액티비티`, `기타`.
- `trip_plan_votes`는 비범위(YAGNI, spec상 옵션).

## 엔드포인트 계약 (기존 api/trips.py 라우터에 추가, prefix `/api/trips`)

- `POST /api/trips/{trip_id}/plan-items` — 항목 추가(멤버). body `{day, time?, place, category, memo?}`. added_by=현재유저. → 항목 dict.
- `GET /api/trips/{trip_id}/plan-items` — 항목 목록(멤버). day→time→created_at 정렬. → `{plan_items: [...]}`.
- `PATCH /api/trips/{trip_id}/plan-items/{item_id}` — 수정(작성자 또는 owner). body 부분 갱신. → 항목 dict.
- `DELETE /api/trips/{trip_id}/plan-items/{item_id}` — 삭제(작성자 또는 owner). → `{deleted: true}`.

비로그인 → 401. 비멤버 → 403. Trip/항목 미존재 → 404. 잘못된 category → 400. 권한 없음(수정/삭제) → 403.

## File Structure

- `api/trip_plan_logic.py` (Create) — 순수 헬퍼: `ALLOWED_CATEGORIES`, `is_valid_category`, `serialize_plan_item`, `can_edit_item(item, user_id, trip_role)`. 비의존.
- `api/trip_plan_service.py` (Create) — orchestration: `add_plan_item`, `list_plan_items`, `update_plan_item`, `delete_plan_item`. 주입 repo, 도메인 예외(`PlanItemNotFound`, `PlanItemForbidden`, `InvalidPlanItem`) + Phase 5 `TripNotFound`/`TripForbidden` 재사용(import).
- `utils/db.py` (Modify) — `trip_plan_items` DDL + `db_create_plan_item`/`db_list_plan_items`/`db_get_plan_item`/`db_update_plan_item`/`db_delete_plan_item`.
- `api/trips.py` (Modify) — `_DbRepo`에 plan-item 메서드 5개 추가 + plan-item 엔드포인트 4개 + Pydantic 모델 2종.
- `tests/test_trip_plan_logic.py` (Create) — 순수 로직(로컬).
- `tests/test_trip_plan_service.py` (Create) — 서비스 + 가짜 repo(로컬).
- `tests/test_trip_plan_api.py` (Create) — 라우터(`importorskip("fastapi")`, CI).
- `cowork/backend/db-schema.md`, `cowork/backend/api-reference.md`, `.github/workflows/main-tests.yml`, `tasklist.md` (Modify, Task 6).

repo 인터페이스(서비스가 기대; FakeRepo와 _DbRepo가 동일 구현):
```
get_trip(trip_id) -> dict | None              # Phase 5 기존
get_member_role(trip_id, user_id) -> str|None # Phase 5 기존
create_plan_item(trip_id, day, time, place, category, added_by, memo) -> dict
list_plan_items(trip_id) -> list[dict]
get_plan_item(item_id) -> dict | None
update_plan_item(item_id, day, time, place, category, memo) -> dict | None
delete_plan_item(item_id) -> None
```

---

### Task 1: 순수 헬퍼 (`api/trip_plan_logic.py`)

**Files:**
- Create: `api/trip_plan_logic.py`
- Test: `tests/test_trip_plan_logic.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trip_plan_logic.py`:

```python
"""tests/test_trip_plan_logic.py — 공동 플래너 순수 헬퍼 테스트"""
from api import trip_plan_logic as L


def test_allowed_categories():
    assert "관광" in L.ALLOWED_CATEGORIES
    assert "식사" in L.ALLOWED_CATEGORIES
    assert "이동" in L.ALLOWED_CATEGORIES
    assert "숙소" in L.ALLOWED_CATEGORIES

def test_is_valid_category():
    assert L.is_valid_category("관광") is True
    assert L.is_valid_category("기타") is True
    assert L.is_valid_category("아무거나") is False
    assert L.is_valid_category("") is False
    assert L.is_valid_category(None) is False

def test_serialize_plan_item():
    row = {"id": 5, "trip_id": "t1", "day": 1, "time": "09:00", "place": "우붓",
           "category": "관광", "memo": "아침 일찍", "added_by": "u1",
           "created_at": "2026-06-14T00:00:00Z"}
    out = L.serialize_plan_item(row)
    assert out["id"] == 5
    assert out["trip_id"] == "t1"
    assert out["day"] == 1
    assert out["place"] == "우붓"
    assert out["category"] == "관광"
    assert out["added_by"] == "u1"

def test_can_edit_item_author():
    item = {"added_by": "u1"}
    assert L.can_edit_item(item, "u1", "member") is True   # 작성자

def test_can_edit_item_owner():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", "owner") is True    # owner는 타인 항목도 가능

def test_can_edit_item_other_member_denied():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", "member") is False  # 타인 + 비owner

def test_can_edit_item_non_member_denied():
    item = {"added_by": "u2"}
    assert L.can_edit_item(item, "u1", None) is False
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_logic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.trip_plan_logic'`

- [ ] **Step 3: 구현** — Create `api/trip_plan_logic.py`:

```python
"""api/trip_plan_logic.py — 공동 플래너(plan item) 순수 헬퍼 (DB/FastAPI 비의존)."""
from __future__ import annotations

ALLOWED_CATEGORIES = ("관광", "식사", "이동", "숙소", "액티비티", "기타")


def is_valid_category(category) -> bool:
    """category가 허용 목록에 있는지."""
    return category in ALLOWED_CATEGORIES


def serialize_plan_item(row: dict) -> dict:
    """plan item DB row → API 응답 dict."""
    return {
        "id": row.get("id"),
        "trip_id": row.get("trip_id"),
        "day": row.get("day"),
        "time": row.get("time"),
        "place": row.get("place"),
        "category": row.get("category"),
        "memo": row.get("memo"),
        "added_by": row.get("added_by"),
        "created_at": row.get("created_at"),
    }


def can_edit_item(item: dict, user_id: str, trip_role: str | None) -> bool:
    """수정/삭제 권한: 항목 작성자이거나 Trip owner."""
    if item.get("added_by") == user_id:
        return True
    return trip_role == "owner"
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_logic.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/trip_plan_logic.py tests/test_trip_plan_logic.py
git commit -m "feat(planner): 공동 플래너 순수 헬퍼 (카테고리·직렬화·편집권한)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 서비스 — 추가/목록 (`api/trip_plan_service.py`)

**Files:**
- Create: `api/trip_plan_service.py`
- Test: `tests/test_trip_plan_service.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trip_plan_service.py`:

```python
"""tests/test_trip_plan_service.py — 공동 플래너 서비스 테스트 (가짜 repo)"""
import pytest
from api import trip_plan_service as SVC


class FakeRepo:
    def __init__(self):
        self.trips = {"t1": {"id": "t1", "owner_user_id": "u1"}}
        self.roles = {("t1", "u1"): "owner", ("t1", "u2"): "member"}
        self.items = {}
        self._seq = 0

    # Phase 5 기존 메서드 (일부)
    def get_trip(self, trip_id):
        return self.trips.get(trip_id)

    def get_member_role(self, trip_id, user_id):
        return self.roles.get((trip_id, user_id))

    # plan-item 메서드
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


# ---------- add_plan_item ----------

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


# ---------- list_plan_items ----------

def test_list_plan_items_sorted(repo):
    SVC.add_plan_item(repo, "t1", "u1", day=2, time="10:00", place="B", category="식사", memo=None)
    SVC.add_plan_item(repo, "t1", "u1", day=1, time="09:00", place="A", category="관광", memo=None)
    out = SVC.list_plan_items(repo, "t1", "u1")
    assert [i["place"] for i in out] == ["A", "B"]

def test_list_plan_items_non_member_forbidden(repo):
    with pytest.raises(SVC.TripForbidden):
        SVC.list_plan_items(repo, "t1", "stranger")
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.trip_plan_service'`

- [ ] **Step 3: 구현** — Create `api/trip_plan_service.py` (NOTE: implements add/list/update/delete fully; update/delete tested in Task 3):

```python
"""api/trip_plan_service.py — 공동 플래너 orchestration (주입 repo, DB/FastAPI 비의존).

Trip 멤버십(Phase 5)을 재사용. repo는 get_trip/get_member_role(기존) +
create_plan_item/list_plan_items/get_plan_item/update_plan_item/delete_plan_item 제공.
"""
from __future__ import annotations

from api import trip_plan_logic as L
from api.trips_service import TripNotFound, TripForbidden
from api import trips_logic as TL


class PlanItemNotFound(Exception):
    pass


class PlanItemForbidden(Exception):
    pass


class InvalidPlanItem(Exception):
    pass


def _require_member(repo, trip_id: str, user_id: str) -> str:
    """Trip 존재 + 멤버 확인. 역할 문자열 반환. 미존재→TripNotFound, 비멤버→TripForbidden."""
    if repo.get_trip(trip_id) is None:
        raise TripNotFound(trip_id)
    role = repo.get_member_role(trip_id, user_id)
    if not TL.is_member_role(role):
        raise TripForbidden(trip_id)
    return role


def add_plan_item(repo, trip_id: str, user_id: str, day: int, time,
                  place: str, category: str, memo) -> dict:
    """계획 항목 추가(멤버). 잘못된 category/빈 place → InvalidPlanItem."""
    _require_member(repo, trip_id, user_id)
    if not L.is_valid_category(category):
        raise InvalidPlanItem(f"invalid category: {category}")
    if not place or not place.strip():
        raise InvalidPlanItem("place is required")
    row = repo.create_plan_item(trip_id, day, time, place.strip(), category, user_id, memo)
    return L.serialize_plan_item(row)


def list_plan_items(repo, trip_id: str, user_id: str) -> list[dict]:
    """계획 항목 목록(멤버)."""
    _require_member(repo, trip_id, user_id)
    return [L.serialize_plan_item(r) for r in repo.list_plan_items(trip_id)]


def _load_editable_item(repo, trip_id: str, item_id, user_id: str) -> dict:
    """수정/삭제 공통: 멤버 확인 + 항목 존재/소속/권한 확인 후 item 반환."""
    role = _require_member(repo, trip_id, user_id)
    item = repo.get_plan_item(item_id)
    if item is None or item.get("trip_id") != trip_id:
        raise PlanItemNotFound(item_id)
    if not L.can_edit_item(item, user_id, role):
        raise PlanItemForbidden(item_id)
    return item


def update_plan_item(repo, trip_id: str, item_id, user_id: str, *, day, time,
                     place, category, memo) -> dict:
    """계획 항목 수정(작성자 또는 owner). 부분 갱신은 호출자가 기존값과 병합해 전달."""
    _load_editable_item(repo, trip_id, item_id, user_id)
    if not L.is_valid_category(category):
        raise InvalidPlanItem(f"invalid category: {category}")
    if not place or not place.strip():
        raise InvalidPlanItem("place is required")
    row = repo.update_plan_item(item_id, day, time, place.strip(), category, memo)
    if row is None:
        raise PlanItemNotFound(item_id)
    return L.serialize_plan_item(row)


def delete_plan_item(repo, trip_id: str, item_id, user_id: str) -> None:
    """계획 항목 삭제(작성자 또는 owner)."""
    _load_editable_item(repo, trip_id, item_id, user_id)
    repo.delete_plan_item(item_id)
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_service.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/trip_plan_service.py tests/test_trip_plan_service.py
git commit -m "feat(planner): 계획 항목 추가/목록 서비스 (멤버 권한·검증)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 서비스 — 수정/삭제 테스트

**Files:**
- Modify: (구현은 Task 2에 포함됨)
- Test: `tests/test_trip_plan_service.py`

- [ ] **Step 1: 실패 테스트 추가** — Append to `tests/test_trip_plan_service.py`:

```python
# ---------- update / delete ----------

def _seed_item(repo, added_by="u2"):
    return SVC.add_plan_item(repo, "t1", added_by, day=1, time="09:00",
                             place="우붓", category="관광", memo="원본")

def test_update_by_author_ok(repo):
    item = _seed_item(repo, added_by="u2")
    out = SVC.update_plan_item(repo, "t1", item["id"], "u2", day=1, time="10:00",
                               place="짱구", category="식사", memo="수정")
    assert out["place"] == "짱구"
    assert out["category"] == "식사"

def test_update_by_owner_ok(repo):
    item = _seed_item(repo, added_by="u2")
    out = SVC.update_plan_item(repo, "t1", item["id"], "u1", day=1, time="10:00",
                               place="짱구", category="식사", memo=None)
    assert out["place"] == "짱구"

def test_update_by_other_member_forbidden(repo):
    item = _seed_item(repo, added_by="u1")  # owner가 작성
    # u2(member)가 타인 항목 수정 시도 → 권한 없음
    with pytest.raises(SVC.PlanItemForbidden):
        SVC.update_plan_item(repo, "t1", item["id"], "u2", day=1, time=None,
                             place="X", category="관광", memo=None)

def test_update_missing_item_notfound(repo):
    with pytest.raises(SVC.PlanItemNotFound):
        SVC.update_plan_item(repo, "t1", 9999, "u1", day=1, time=None,
                             place="X", category="관광", memo=None)

def test_update_invalid_category(repo):
    item = _seed_item(repo, added_by="u1")
    with pytest.raises(SVC.InvalidPlanItem):
        SVC.update_plan_item(repo, "t1", item["id"], "u1", day=1, time=None,
                             place="X", category="없는카테고리", memo=None)

def test_update_non_member_forbidden(repo):
    item = _seed_item(repo, added_by="u1")
    with pytest.raises(SVC.TripForbidden):
        SVC.update_plan_item(repo, "t1", item["id"], "stranger", day=1, time=None,
                             place="X", category="관광", memo=None)

def test_delete_by_author_ok(repo):
    item = _seed_item(repo, added_by="u2")
    SVC.delete_plan_item(repo, "t1", item["id"], "u2")
    assert repo.get_plan_item(item["id"]) is None

def test_delete_by_other_member_forbidden(repo):
    item = _seed_item(repo, added_by="u1")
    with pytest.raises(SVC.PlanItemForbidden):
        SVC.delete_plan_item(repo, "t1", item["id"], "u2")

def test_delete_missing_item_notfound(repo):
    with pytest.raises(SVC.PlanItemNotFound):
        SVC.delete_plan_item(repo, "t1", 9999, "u1")

def test_item_from_other_trip_notfound(repo):
    # 다른 trip의 item_id로 접근하면 소속 불일치 → PlanItemNotFound
    item = _seed_item(repo, added_by="u1")
    repo.trips["t2"] = {"id": "t2", "owner_user_id": "u1"}
    repo.roles[("t2", "u1")] = "owner"
    with pytest.raises(SVC.PlanItemNotFound):
        SVC.update_plan_item(repo, "t2", item["id"], "u1", day=1, time=None,
                             place="X", category="관광", memo=None)
```

- [ ] **Step 2: 통과 확인** (구현은 Task 2에 포함됨)

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_service.py -v`
Expected: PASS (7 + 10 = 17 passed)

실패 시 Task 2의 `update_plan_item`/`delete_plan_item`/`_load_editable_item`를 위 테스트와 대조해 수정.

- [ ] **Step 3: 커밋**

```bash
git add tests/test_trip_plan_service.py
git commit -m "test(planner): 계획 항목 수정/삭제 권한·소속 검증 고정

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: DB repo (`utils/db.py` DDL + SQL)

**Files:**
- Modify: `utils/db.py`

> Postgres 부재로 자동검증 불가 — 배포 검증. ast.parse만. Phase 5의 trip 테이블 DDL/repo 패턴을 정확히 따른다.

- [ ] **Step 1: DDL 추가** — In `utils/db.py` `init_db()`, immediately AFTER the `cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_invites_trip ON trip_invites(trip_id);")` line (the last Phase-5 trip DDL, before `backfill_legacy_user_identity(conn)`), add:

```python
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trip_plan_items (
                id         SERIAL PRIMARY KEY,
                trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                day        INTEGER NOT NULL,
                time       TEXT,
                place      TEXT NOT NULL,
                category   TEXT NOT NULL,
                memo       TEXT,
                added_by   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_plan_items_trip ON trip_plan_items(trip_id);")
```

VERIFY by reading the surrounding lines that the insertion is inside the cursor block and after the trip_invites index.

- [ ] **Step 2: SQL repo 함수 추가** — Append to the END of `utils/db.py` (Json/RealDictCursor are module-level imports already; do NOT add lazy imports):

```python
def db_create_plan_item(trip_id: str, day: int, time, place: str, category: str, added_by: str, memo) -> dict:
    """trip_plan_items 행 삽입 후 dict 반환."""
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO trip_plan_items (trip_id, day, time, place, category, added_by, memo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, trip_id, day, time, place, category, memo, added_by, created_at;
            """,
            (trip_id, day, time, place, category, added_by, memo),
        )
        row = cur.fetchone()
    conn.commit()
    return dict(row)


def db_list_plan_items(trip_id: str) -> list[dict]:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, trip_id, day, time, place, category, memo, added_by, created_at "
            "FROM trip_plan_items WHERE trip_id = %s "
            "ORDER BY day, time NULLS LAST, id;",
            (trip_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def db_get_plan_item(item_id) -> dict | None:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, trip_id, day, time, place, category, memo, added_by, created_at "
            "FROM trip_plan_items WHERE id = %s;",
            (item_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def db_update_plan_item(item_id, day: int, time, place: str, category: str, memo) -> dict | None:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            UPDATE trip_plan_items
            SET day = %s, time = %s, place = %s, category = %s, memo = %s
            WHERE id = %s
            RETURNING id, trip_id, day, time, place, category, memo, added_by, created_at;
            """,
            (day, time, place, category, memo, item_id),
        )
        row = cur.fetchone()
    conn.commit()
    return dict(row) if row else None


def db_delete_plan_item(item_id) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM trip_plan_items WHERE id = %s;", (item_id,))
    conn.commit()
```

- [ ] **Step 3: 문법 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -c "import ast; ast.parse(open('utils/db.py').read()); print('utils/db.py syntax OK')"`
Expected: `utils/db.py syntax OK`

- [ ] **Step 4: 커밋**

```bash
git add utils/db.py
git commit -m "feat(planner): trip_plan_items 테이블 DDL + SQL repo 함수

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 라우터 엔드포인트 + _DbRepo 확장 (`api/trips.py`)

**Files:**
- Modify: `api/trips.py`
- Test: `tests/test_trip_plan_api.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trip_plan_api.py`:

```python
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
    resp = _client().patch("/api/trips/t1/plan-items/9",
                           json={"day": 1, "place": "X", "category": "관광"})
    assert resp.status_code == 404


def test_update_plan_item_forbidden_maps_403(monkeypatch):
    monkeypatch.setattr(trips_mod, "_repo", lambda: object())
    def boom(repo, tid, item_id, uid, **kw):
        raise PSVC.PlanItemForbidden(item_id)
    monkeypatch.setattr(PSVC, "update_plan_item", boom)
    resp = _client().patch("/api/trips/t1/plan-items/9",
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
```

- [ ] **Step 2: 실패 확인 (로컬 skip)**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_api.py -q`
Expected (로컬): skipped. CI: FAIL (엔드포인트 미존재).

- [ ] **Step 3: _DbRepo 확장** — In `api/trips.py`, add these 5 methods to the `_DbRepo` class (after the existing `get_invite` method, same lazy-import style):

```python
    def create_plan_item(self, trip_id, day, time, place, category, added_by, memo):
        from utils.db import db_create_plan_item
        return db_create_plan_item(trip_id, day, time, place, category, added_by, memo)

    def list_plan_items(self, trip_id):
        from utils.db import db_list_plan_items
        return db_list_plan_items(trip_id)

    def get_plan_item(self, item_id):
        from utils.db import db_get_plan_item
        return db_get_plan_item(item_id)

    def update_plan_item(self, item_id, day, time, place, category, memo):
        from utils.db import db_update_plan_item
        return db_update_plan_item(item_id, day, time, place, category, memo)

    def delete_plan_item(self, item_id):
        from utils.db import db_delete_plan_item
        return db_delete_plan_item(item_id)
```

- [ ] **Step 4: 엔드포인트 + 모델 추가** — In `api/trips.py`, add the import for the plan service near the existing `from api import trips_service as SVC` line:

```python
from api import trip_plan_service as PSVC
```

Add Pydantic models near the existing `JoinRequest` model:

```python
class PlanItemCreateRequest(BaseModel):
    day: int = Field(ge=1, le=60)
    time: str | None = Field(default=None, max_length=20)
    place: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=20)
    memo: str | None = Field(default=None, max_length=500)


class PlanItemUpdateRequest(BaseModel):
    day: int = Field(ge=1, le=60)
    time: str | None = Field(default=None, max_length=20)
    place: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=20)
    memo: str | None = Field(default=None, max_length=500)
```

Add these 4 endpoints at the END of `api/trips.py`:

```python
@router.post("/{trip_id}/plan-items")
async def add_plan_item(trip_id: str, req: PlanItemCreateRequest, request: Request):
    user_id = _require_user(request)
    try:
        return PSVC.add_plan_item(_repo(), trip_id, user_id, day=req.day, time=req.time,
                                  place=req.place, category=req.category, memo=req.memo)
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.InvalidPlanItem as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{trip_id}/plan-items")
async def list_plan_items(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return {"plan_items": PSVC.list_plan_items(_repo(), trip_id, user_id)}
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.patch("/{trip_id}/plan-items/{item_id}")
async def update_plan_item(trip_id: str, item_id: int, req: PlanItemUpdateRequest, request: Request):
    user_id = _require_user(request)
    try:
        return PSVC.update_plan_item(_repo(), trip_id, item_id, user_id, day=req.day,
                                     time=req.time, place=req.place, category=req.category,
                                     memo=req.memo)
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.PlanItemNotFound:
        raise HTTPException(status_code=404, detail="Plan item not found.")
    except PSVC.PlanItemForbidden:
        raise HTTPException(status_code=403, detail="No permission to edit this item.")
    except PSVC.InvalidPlanItem as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{trip_id}/plan-items/{item_id}")
async def delete_plan_item(trip_id: str, item_id: int, request: Request):
    user_id = _require_user(request)
    try:
        PSVC.delete_plan_item(_repo(), trip_id, item_id, user_id)
        return {"deleted": True}
    except PSVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except PSVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")
    except PSVC.PlanItemNotFound:
        raise HTTPException(status_code=404, detail="Plan item not found.")
    except PSVC.PlanItemForbidden:
        raise HTTPException(status_code=403, detail="No permission to delete this item.")
```

> NOTE: `PSVC.TripNotFound`/`PSVC.TripForbidden` are the same classes as `trips_service.TripNotFound/TripForbidden` (re-exported via `trip_plan_service`'s `from api.trips_service import ...`), so catching `PSVC.TripForbidden` works. The router tests monkeypatch `PSVC.*` functions and reference `PSVC.InvalidPlanItem`/`PSVC.PlanItemNotFound`/`PSVC.PlanItemForbidden`/`PSVC.TripForbidden` — all must be importable attributes of `trip_plan_service`.

- [ ] **Step 5: 검증**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_api.py -q` → expect skipped (로컬).
Run: `SKIP_EXTERNAL_INIT=1 python3 -c "import ast; ast.parse(open('api/trips.py').read()); print('syntax OK')"` → expect `syntax OK`.

- [ ] **Step 6: 커밋**

```bash
git add api/trips.py tests/test_trip_plan_api.py
git commit -m "feat(planner): /api/trips/{id}/plan-items 엔드포인트(추가·목록·수정·삭제)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 문서 동기화 + CI 등록 + 작업 로그

**Files:**
- Modify: `cowork/backend/db-schema.md`, `cowork/backend/api-reference.md`, `.github/workflows/main-tests.yml`, `tasklist.md`

- [ ] **Step 1: db-schema.md** — (a) Add a row to the "## 테이블 목록" table after the `trip_invites` row:
```
| `trip_plan_items` | 공동 여행 계획 항목(Day별 장소·카테고리) |
```
(b) Add a `## trip_plan_items` section before the "## 인덱스" section, mirroring the `## trip_invites` format, with the DDL from Task 4 Step 1 and a column table:

```markdown
## trip_plan_items

Trip 멤버들이 공동으로 작성하는 Day별 계획 항목. 추가/조회는 멤버, 수정/삭제는 작성자 또는 owner.

```sql
CREATE TABLE IF NOT EXISTS trip_plan_items (
    id         SERIAL PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day        INTEGER NOT NULL,
    time       TEXT,
    place      TEXT NOT NULL,
    category   TEXT NOT NULL,
    memo       TEXT,
    added_by   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trip_plan_items_trip ON trip_plan_items(trip_id);
```

| 컬럼 | 타입 | Null | 설명 |
|------|------|------|------|
| `id` | SERIAL PK | NOT NULL | 자동 증가 정수 |
| `trip_id` | TEXT FK→trips(id) | NOT NULL | ON DELETE CASCADE |
| `day` | INTEGER | NOT NULL | 여행 Day (1부터) |
| `time` | TEXT | NULL 가능 | 시간 (예: '09:00' 또는 '오전') |
| `place` | TEXT | NOT NULL | 장소/활동명 |
| `category` | TEXT | NOT NULL | 관광·식사·이동·숙소·액티비티·기타 |
| `memo` | TEXT | NULL 가능 | 메모 |
| `added_by` | TEXT FK→users(id) | NOT NULL | 작성자, ON DELETE CASCADE |
| `created_at` | TIMESTAMPTZ | NOT NULL | 생성 시각 (기본값 NOW()) |

---
```

(c) Add an index row to the "## 인덱스" table:
```
| `idx_trip_plan_items_trip` | `trip_plan_items` | `trip_id` | 여행별 계획 항목 조회 |
```
(d) In "## 관계", add under the `trips (id)` block: `  └── trip_plan_items (trip_id) — 1:N`.

- [ ] **Step 2: api-reference.md** — In the "## Trip & 동행 초대 API (신규)" section, append the 4 plan-item endpoints (after the `POST /api/trips/join` subsection):

```markdown
### POST /api/trips/{trip_id}/plan-items

공동 계획 항목 추가(멤버). Request: `{"day": 1, "time": "09:00", "place": "우붓", "category": "관광", "memo": "아침"}`
- `category` 허용값: 관광·식사·이동·숙소·액티비티·기타. `day` 1~60, `place` 필수.
- Response 200: 항목 dict (`{"id": 1, "trip_id": "...", "day": 1, "time": "...", "place": "...", "category": "...", "memo": "...", "added_by": "...", "created_at": "..."}`).
- `400` 잘못된 category/빈 place / `403` 비멤버 / `404` Trip 미존재.

### GET /api/trips/{trip_id}/plan-items

계획 항목 목록(멤버). day→time→id 정렬. Response 200: `{"plan_items": [ ... ]}`. `403`/`404` 동일.

### PATCH /api/trips/{trip_id}/plan-items/{item_id}

항목 수정(작성자 또는 owner). Request: 생성과 동일 필드(전체 전달). Response 200: 수정된 항목.
- `400` 잘못된 입력 / `403` 권한 없음 / `404` Trip/항목 미존재.

### DELETE /api/trips/{trip_id}/plan-items/{item_id}

항목 삭제(작성자 또는 owner). Response 200: `{"deleted": true}`. `403`/`404` 동일.
```

- [ ] **Step 3: CI 등록** — In `.github/workflows/main-tests.yml`, after `tests/test_trips_service.py \`, add:
```
            tests/test_trip_plan_logic.py \
            tests/test_trip_plan_service.py \
            tests/test_trip_plan_api.py \
```
Also add `api/trips.py` is already in the py_compile syntax-check line; no change needed there.

- [ ] **Step 4: 작업 로그** — Append to the END of the `## 2026-06-14` section in `tasklist.md`:
```markdown
- Phase 6(공동 플래너) 완료: `trip_plan_items` 테이블 + SQL repo, `api/trip_plan_logic.py`(카테고리·직렬화·편집권한)·`api/trip_plan_service.py`(추가/목록/수정/삭제, Trip 멤버십 재사용) 신설, `api/trips.py`에 `/plan-items` 엔드포인트 4개 추가. `db-schema.md`·`api-reference.md` 동기화.
- 로직/서비스 테스트 24개(로컬, 가짜 repo) + 라우터 테스트 9개(CI 전용) + CI 등록. 권한: 추가/조회=멤버, 수정/삭제=작성자 또는 owner. SQL은 Railway 배포 시 검증.
```

- [ ] **Step 5: 전체 회귀 (로컬)** — Run:
`SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trip_plan_logic.py tests/test_trip_plan_service.py tests/test_trip_plan_api.py -q`
Expected: logic 7 + service 17 + api skipped = **24 passed, (api) skipped**.

- [ ] **Step 6: CI 등록 확인** — Run:
`grep -n "test_trip_plan" .github/workflows/main-tests.yml`
Expected: 3 줄.

- [ ] **Step 7: 커밋**

```bash
git add cowork/backend/db-schema.md cowork/backend/api-reference.md .github/workflows/main-tests.yml tasklist.md
git commit -m "docs(planner): db-schema·api-reference 동기화 + CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (Phase 6 = trip_plan_items + 협업 일정 API):**
- spec `trip_plan_items`(day/time/place/category/added_by/memo/created_at) → Task 4 DDL ✅
- spec 멤버들이 Day별 계획 항목 추가 → `POST /plan-items` + add_plan_item ✅
- spec 항목 조회/수정/삭제(협업) → GET/PATCH/DELETE + service ✅
- spec category(관광·식사·이동·숙소) → ALLOWED_CATEGORIES(+액티비티·기타) 검증 ✅
- spec '추가한 사람' → added_by(현재 유저) ✅
- spec trip_plan_votes(옵션) → 비범위(YAGNI) ✅
- 격리: 신규 파일 + trips.py/​utils.db 추가만 ✅
- 문서 동기화 → Task 6 ✅

**2. Placeholder scan:** 코드 step 전부 실제 코드/명령. 문서 step은 미러링 지시 + 구체 내용. TBD 없음. ✅

**3. Type consistency:**
- repo 메서드명(create_plan_item/list_plan_items/get_plan_item/update_plan_item/delete_plan_item) — FakeRepo·_DbRepo·db_* 함수·service 호출 일치 ✅
- service 시그니처: `add_plan_item(repo, trip_id, user_id, day, time, place, category, memo)`, `update_plan_item(repo, trip_id, item_id, user_id, *, day, time, place, category, memo)` — service 정의·service 테스트·라우터 호출 일치. 라우터는 keyword(day=...,time=...)로 호출하므로 update의 keyword-only(*)와 정합 ✅
- 라우터 테스트 monkeypatch는 `update_plan_item(repo, tid, item_id, uid, **kw)` 시그니처로 stub → keyword 호출과 일치 ✅
- 예외: `InvalidPlanItem`/`PlanItemNotFound`/`PlanItemForbidden`는 trip_plan_service 정의, `TripNotFound`/`TripForbidden`는 trips_service에서 import 재노출 → `PSVC.TripForbidden` 접근 가능, 라우터 매핑(400/403/404) 일관 ✅
- DB RETURNING/SELECT 컬럼 9개 일치(id/trip_id/day/time/place/category/memo/added_by/created_at), serialize_plan_item 키와 일치 ✅

**4. 테스트 합계:** logic 7 + service 17(Task2 7 + Task3 10) = 24(로컬). api 9(CI). Phase 6 신규 33. 로컬 회귀 24 passed + api skipped.

**5. 환경 주의(실행자 가이드):** Postgres 부재 → Task 4 SQL은 배포 검증. logic/service는 psycopg2/fastapi 미import(서비스는 repo 주입) → 로컬 통과. 라우터 테스트는 importorskip로 로컬 skip, CI 실행. `_DbRepo` plan-item 메서드는 lazy import 유지.
