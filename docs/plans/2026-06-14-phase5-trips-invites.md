# Phase 5 — Trip 저장 & 동행 초대 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 추천 보고서를 Trip으로 저장하고, 초대 링크를 발급해 친구가 로그인 후 합류하는 협업 기반(테이블 + API)을 구축한다. 공동 일정 항목(plan_items)은 Phase 6.

**Architecture:** DB 의존 코드(psycopg2/Postgres)는 로컬·CI 모두에서 실행 불가(CI에 Postgres 없음 → 배포 시 검증)하므로, 로직을 3계층으로 분리한다 — (1) `api/trips_logic.py` 순수 헬퍼(토큰·만료·권한·직렬화, 로컬 TDD), (2) `api/trips_service.py` orchestration(주입된 repo로 로컬 TDD, 도메인 예외), (3) `utils/db.py` 실제 SQL repo + `api/trips.py` FastAPI 라우터(CI에서 TestClient + 가짜 repo로 검증). 멱등 DDL은 `init_db()`에 추가한다.

**Tech Stack:** FastAPI, psycopg2(PostgreSQL), Pydantic, pytest. 테스트는 `SKIP_EXTERNAL_INIT=1 python3 -m pytest`.

---

## 격리/원칙 (필수)

- 기존 테이블/엔드포인트/이민 경로 **변경 금지**. `init_db()`에는 신규 `CREATE TABLE IF NOT EXISTS`만 추가(멱등).
- 이 프로젝트는 nnai 포크(별도 repo·별도 Railway DB `nnai-travel-prd`) — utils/db.py 수정은 여행 배포에만 영향.
- push는 항상 `develop`. `main` 금지.
- **CLAUDE.md 규칙**: 테이블 추가 → `cowork/backend/db-schema.md` 동기화(Task 6). 엔드포인트 추가 → `cowork/backend/api-reference.md` 동기화(Task 6).
- 새 테스트 파일은 `.github/workflows/main-tests.yml` 등록(Task 6). 작업 로그 `tasklist.md`(Task 6).
- 환경: 로컬에 `fastapi`/`psycopg2` 부재, CI에 존재하나 Postgres 부재. → 순수 로직/서비스만 로컬+CI 자동검증, SQL/라우터는 배포 검증 + CI는 가짜 repo로 라우터 로직만 검증.

## 데이터 모델 (init_db DDL)

```sql
CREATE TABLE IF NOT EXISTS trips (
    id            TEXT PRIMARY KEY,           -- 토큰형 ID
    owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title         TEXT NOT NULL DEFAULT '',
    destination   JSONB NOT NULL,             -- 추천 보고서 스냅샷
    start_date    DATE,
    end_date      DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS trip_members (
    trip_id   TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      TEXT NOT NULL DEFAULT 'member',  -- owner | member
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trip_id, user_id)
);
CREATE TABLE IF NOT EXISTS trip_invites (
    token      TEXT PRIMARY KEY,
    trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trip_members_user ON trip_members(user_id);
CREATE INDEX IF NOT EXISTS idx_trip_invites_trip ON trip_invites(trip_id);
```

> 초대 링크는 만료(기본 14일) 전까지 **재사용 가능**(그룹 다수 합류). spec의 단일-사용 `used_at` 대신 만료 기반 멀티유즈로 단순화(YAGNI). 합류는 멱등(재합류=무효과).

## 엔드포인트 계약 (api/trips.py, prefix `/api/trips`)

- `POST /api/trips` — Trip 생성. body `{title?, destination(dict), start_date?, end_date?}`. owner=현재유저. → trip dict. (로그인 필요)
- `GET /api/trips` — 내가 owner/member인 Trip 목록. → `{trips: [...]}`.
- `GET /api/trips/{trip_id}` — Trip 상세 + 멤버. 멤버 아니면 403. → trip dict + members.
- `POST /api/trips/{trip_id}/invites` — 초대 링크 발급(멤버만). → `{token, invite_url, expires_at}`.
- `POST /api/trips/join` — body `{token}`. 현재 유저를 멤버로 추가. 만료/무효 토큰 → 400/410. → joined trip dict.

비로그인 → 401. 권한 위반 → 403. 미존재 → 404. 만료 초대 → 410.

## File Structure

- `api/trips_logic.py` (Create) — 순수 헬퍼: `generate_trip_id`, `generate_invite_token`, `invite_expiry`, `is_invite_expired`, `build_invite_url`, `serialize_trip`, 권한 상수/`is_member_role`. fastapi/psycopg2 비의존.
- `api/trips_service.py` (Create) — orchestration: `create_trip`, `list_trips`, `get_trip_detail`, `create_invite`, `join_trip`. 주입된 `repo`(duck-typed) 사용, 도메인 예외(`TripNotFound`, `TripForbidden`, `InviteExpired`, `InviteInvalid`). fastapi/psycopg2 비의존.
- `utils/db.py` (Modify) — DDL 추가 + 실제 SQL repo 함수(`db_create_trip` 등). psycopg2(CI/배포).
- `api/trips.py` (Create) — FastAPI 라우터 + Pydantic 모델 + `_DbRepo` 어댑터. 서비스 호출·예외 매핑·auth 게이팅.
- `server.py` (Modify) — include_router.
- `tests/test_trips_logic.py` (Create) — 순수 헬퍼(로컬).
- `tests/test_trips_service.py` (Create) — 서비스 + 가짜 repo(로컬).
- `tests/test_trips_api.py` (Create) — 라우터(`importorskip("fastapi")`, 가짜 service/repo, CI).
- `cowork/backend/db-schema.md`, `cowork/backend/api-reference.md`, `.github/workflows/main-tests.yml`, `tasklist.md` (Modify, Task 6).

repo 인터페이스(서비스가 기대하는 duck-typed 메서드):
```
create_trip(owner_user_id, title, destination, start_date, end_date) -> dict(trip row)
get_trip(trip_id) -> dict | None
list_trips_for_user(user_id) -> list[dict]
get_member_role(trip_id, user_id) -> str | None
get_members(trip_id) -> list[dict]   # [{user_id, role, joined_at}]
add_member(trip_id, user_id, role) -> None   # 멱등(ON CONFLICT DO NOTHING)
create_invite(token, trip_id, created_by, expires_at) -> dict
get_invite(token) -> dict | None     # {token, trip_id, created_by, expires_at}
```

---

### Task 1: 순수 헬퍼 (`api/trips_logic.py`)

**Files:**
- Create: `api/trips_logic.py`
- Test: `tests/test_trips_logic.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trips_logic.py`:

```python
"""tests/test_trips_logic.py — Trip 순수 헬퍼 테스트 (DB/fastapi 불필요)"""
from datetime import datetime, timezone, timedelta
from api import trips_logic as L


def test_generate_trip_id_unique_and_urlsafe():
    a, b = L.generate_trip_id(), L.generate_trip_id()
    assert a != b
    assert len(a) >= 16
    assert all(c.isalnum() or c in "-_" for c in a)

def test_generate_invite_token_unique():
    assert L.generate_invite_token() != L.generate_invite_token()
    assert len(L.generate_invite_token()) >= 24

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
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_logic.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.trips_logic'`

- [ ] **Step 3: 구현** — Create `api/trips_logic.py`:

```python
"""api/trips_logic.py — Trip/초대 순수 헬퍼 (DB/FastAPI 비의존)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

_MEMBER_ROLES = {"owner", "member"}


def generate_trip_id() -> str:
    """URL-safe 한 Trip ID."""
    return secrets.token_urlsafe(12)


def generate_invite_token() -> str:
    """URL-safe 한 초대 토큰."""
    return secrets.token_urlsafe(24)


def invite_expiry(now: datetime, days: int = 14) -> datetime:
    """현재 시각 기준 초대 만료 시각."""
    return now + timedelta(days=days)


def is_invite_expired(expires_at: datetime, now: datetime) -> bool:
    """만료 여부."""
    return expires_at <= now


def build_invite_url(base_url: str, token: str) -> str:
    """프론트 합류 링크 생성."""
    return f"{base_url.rstrip('/')}/trips/join?token={token}"


def is_member_role(role: str | None) -> bool:
    """유효한 멤버 역할인지(=Trip 접근 권한 보유)."""
    return role in _MEMBER_ROLES


def serialize_trip(trip: dict, members: list[dict]) -> dict:
    """Trip row + 멤버 목록 → API 응답 dict."""
    return {
        "id": trip.get("id"),
        "owner_user_id": trip.get("owner_user_id"),
        "title": trip.get("title", ""),
        "destination": trip.get("destination"),
        "start_date": trip.get("start_date"),
        "end_date": trip.get("end_date"),
        "created_at": trip.get("created_at"),
        "members": members,
    }
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_logic.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/trips_logic.py tests/test_trips_logic.py
git commit -m "feat(trips): Trip/초대 순수 헬퍼 (토큰·만료·권한·직렬화)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 서비스 — Trip 생성/조회/목록 (`api/trips_service.py`)

**Files:**
- Create: `api/trips_service.py`
- Test: `tests/test_trips_service.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trips_service.py`:

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.trips_service'`

- [ ] **Step 3: 구현** — Create `api/trips_service.py`:

```python
"""api/trips_service.py — Trip orchestration (주입 repo, DB/FastAPI 비의존).

repo는 duck-typed: create_trip/get_trip/list_trips_for_user/get_member_role/
get_members/add_member/create_invite/get_invite 를 제공한다.
"""
from __future__ import annotations

from datetime import datetime, timezone

from api import trips_logic as L


class TripNotFound(Exception):
    pass


class TripForbidden(Exception):
    pass


class InviteInvalid(Exception):
    pass


class InviteExpired(Exception):
    pass


def create_trip(repo, owner_user_id: str, title: str, destination: dict,
                start_date, end_date) -> dict:
    """Trip 생성 + owner 멤버 등록 → 직렬화된 trip."""
    trip = repo.create_trip(owner_user_id, title or "", destination, start_date, end_date)
    repo.add_member(trip["id"], owner_user_id, "owner")
    return L.serialize_trip(trip, repo.get_members(trip["id"]))


def list_trips(repo, user_id: str) -> list[dict]:
    """유저가 멤버인 Trip 목록(직렬화)."""
    trips = repo.list_trips_for_user(user_id)
    return [L.serialize_trip(t, repo.get_members(t["id"])) for t in trips]


def get_trip_detail(repo, trip_id: str, user_id: str) -> dict:
    """Trip 상세. 미존재 → TripNotFound, 비멤버 → TripForbidden."""
    trip = repo.get_trip(trip_id)
    if trip is None:
        raise TripNotFound(trip_id)
    if not L.is_member_role(repo.get_member_role(trip_id, user_id)):
        raise TripForbidden(trip_id)
    return L.serialize_trip(trip, repo.get_members(trip_id))


def create_invite(repo, trip_id: str, user_id: str, base_url: str,
                  now: datetime | None = None) -> dict:
    """초대 링크 발급(멤버만). → {token, invite_url, expires_at}."""
    trip = repo.get_trip(trip_id)
    if trip is None:
        raise TripNotFound(trip_id)
    if not L.is_member_role(repo.get_member_role(trip_id, user_id)):
        raise TripForbidden(trip_id)
    now = now or datetime.now(timezone.utc)
    token = L.generate_invite_token()
    expires_at = L.invite_expiry(now)
    repo.create_invite(token, trip_id, user_id, expires_at)
    return {"token": token, "invite_url": L.build_invite_url(base_url, token),
            "expires_at": expires_at}


def join_trip(repo, token: str, user_id: str,
              now: datetime | None = None) -> dict:
    """초대 토큰으로 합류. 무효 → InviteInvalid, 만료 → InviteExpired. → trip 상세."""
    invite = repo.get_invite(token)
    if invite is None:
        raise InviteInvalid(token)
    now = now or datetime.now(timezone.utc)
    if L.is_invite_expired(invite["expires_at"], now):
        raise InviteExpired(token)
    trip_id = invite["trip_id"]
    repo.add_member(trip_id, user_id, "member")
    trip = repo.get_trip(trip_id)
    return L.serialize_trip(trip, repo.get_members(trip_id))
```

- [ ] **Step 4: 통과 확인**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_service.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋**

```bash
git add api/trips_service.py tests/test_trips_service.py
git commit -m "feat(trips): Trip 생성/조회/목록 서비스 (주입 repo)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 서비스 — 초대 발급/합류 테스트

**Files:**
- Modify: (구현은 Task 2에 포함됨)
- Test: `tests/test_trips_service.py`

- [ ] **Step 1: 실패 테스트 추가** — Append to `tests/test_trips_service.py`:

```python
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
```

- [ ] **Step 2: 통과 확인** (구현은 Task 2에 포함됨)

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_service.py -v`
Expected: PASS (6 + 7 = 13 passed)

만약 실패하면 Task 2의 `create_invite`/`join_trip` 구현을 위 테스트와 대조해 수정한다.

- [ ] **Step 3: 커밋**

```bash
git add tests/test_trips_service.py
git commit -m "test(trips): 초대 발급/합류 서비스 동작 고정 (만료·멱등)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: DB repo (`utils/db.py` DDL + SQL 함수)

**Files:**
- Modify: `utils/db.py`

> 이 Task는 Postgres 부재로 로컬·CI 자동검증 불가 — 배포 시 검증. 기존 패턴(멱등 DDL, `RETURNING`, `psycopg2.extras` dict cursor)을 정확히 따른다. 테스트 추가 없음(서비스/라우터 테스트가 동작을 고정함).

- [ ] **Step 1: DDL 추가** — In `utils/db.py`, inside `init_db()`, locate the final DDL `cur.execute(...)` block immediately before `backfill_legacy_user_identity(conn)` (the line that runs after the last `CREATE INDEX ... idx_verified_city_external_metrics_city_id`). Add these statements right after that last index creation, still inside the `with conn.cursor() as cur:` block:

```python
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id            TEXT PRIMARY KEY,
                owner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title         TEXT NOT NULL DEFAULT '',
                destination   JSONB NOT NULL,
                start_date    DATE,
                end_date      DATE,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trip_members (
                trip_id   TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role      TEXT NOT NULL DEFAULT 'member',
                joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (trip_id, user_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trip_invites (
                token      TEXT PRIMARY KEY,
                trip_id    TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                created_by TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_members_user ON trip_members(user_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trip_invites_trip ON trip_invites(trip_id);")
```

- [ ] **Step 2: SQL repo 함수 추가** — Append these module-level functions to the END of `utils/db.py`. They use `get_conn()` and `psycopg2.extras.RealDictCursor` (import `psycopg2.extras` at top of file if not already imported — check first; the file already imports `psycopg2`). Use `json.Json` adapter for the JSONB column (the file already imports `json`; use `from psycopg2.extras import Json` locally inside the function if a module import isn't present):

```python
def db_create_trip(trip_id, owner_user_id, title, destination, start_date, end_date) -> dict:
    """trips 행 삽입 후 dict 반환."""
    from psycopg2.extras import Json, RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            INSERT INTO trips (id, owner_user_id, title, destination, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, owner_user_id, title, destination, start_date, end_date, created_at;
            """,
            (trip_id, owner_user_id, title, Json(destination), start_date, end_date),
        )
        row = cur.fetchone()
    conn.commit()
    return dict(row)


def db_get_trip(trip_id) -> dict | None:
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, owner_user_id, title, destination, start_date, end_date, created_at "
            "FROM trips WHERE id = %s;",
            (trip_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def db_list_trips_for_user(user_id) -> list[dict]:
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT t.id, t.owner_user_id, t.title, t.destination, t.start_date,
                   t.end_date, t.created_at
            FROM trips t
            JOIN trip_members m ON m.trip_id = t.id
            WHERE m.user_id = %s
            ORDER BY t.created_at DESC;
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def db_get_member_role(trip_id, user_id) -> str | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT role FROM trip_members WHERE trip_id = %s AND user_id = %s;",
            (trip_id, user_id),
        )
        row = cur.fetchone()
    return row[0] if row else None


def db_get_members(trip_id) -> list[dict]:
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, role, joined_at FROM trip_members "
            "WHERE trip_id = %s ORDER BY joined_at;",
            (trip_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def db_add_member(trip_id, user_id, role) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO trip_members (trip_id, user_id, role) VALUES (%s, %s, %s) "
            "ON CONFLICT (trip_id, user_id) DO NOTHING;",
            (trip_id, user_id, role),
        )
    conn.commit()


def db_create_invite(token, trip_id, created_by, expires_at) -> dict:
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO trip_invites (token, trip_id, created_by, expires_at) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING token, trip_id, created_by, expires_at, created_at;",
            (token, trip_id, created_by, expires_at),
        )
        row = cur.fetchone()
    conn.commit()
    return dict(row)


def db_get_invite(token) -> dict | None:
    from psycopg2.extras import RealDictCursor
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT token, trip_id, created_by, expires_at, created_at "
            "FROM trip_invites WHERE token = %s;",
            (token,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
```

- [ ] **Step 3: 문법 확인** (psycopg2 부재 → import 불가, ast.parse로 문법만)

Run: `SKIP_EXTERNAL_INIT=1 python3 -c "import ast; ast.parse(open('utils/db.py').read()); print('utils/db.py syntax OK')"`
Expected: `utils/db.py syntax OK`

- [ ] **Step 4: 커밋**

```bash
git add utils/db.py
git commit -m "feat(trips): trips/members/invites 테이블 DDL + SQL repo 함수

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: FastAPI 라우터 + server 배선 (`api/trips.py`)

**Files:**
- Create: `api/trips.py`
- Modify: `server.py`
- Test: `tests/test_trips_api.py`

- [ ] **Step 1: 실패 테스트 작성** — Create `tests/test_trips_api.py`:

```python
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
```

- [ ] **Step 2: 실패 확인 (로컬 skip 예상)**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_api.py -v`
Expected (로컬): skipped. CI: FAIL — `No module named 'api.trips'`.

- [ ] **Step 3: 라우터 구현** — Create `api/trips.py`:

```python
"""api/trips.py — Trip 저장/초대 FastAPI 라우터 (얇은 어댑터).

로직은 api/trips_service.py. 이 모듈은 auth 게이팅·예외 매핑·repo 어댑터만 담당.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api import trips_service as SVC
from api import trips_logic as L

router = APIRouter()


class _DbRepo:
    """utils.db SQL 함수를 서비스가 기대하는 repo 인터페이스로 어댑트."""
    def create_trip(self, owner_user_id, title, destination, start_date, end_date):
        from utils.db import db_create_trip
        return db_create_trip(L.generate_trip_id(), owner_user_id, title,
                              destination, start_date, end_date)

    def get_trip(self, trip_id):
        from utils.db import db_get_trip
        return db_get_trip(trip_id)

    def list_trips_for_user(self, user_id):
        from utils.db import db_list_trips_for_user
        return db_list_trips_for_user(user_id)

    def get_member_role(self, trip_id, user_id):
        from utils.db import db_get_member_role
        return db_get_member_role(trip_id, user_id)

    def get_members(self, trip_id):
        from utils.db import db_get_members
        return db_get_members(trip_id)

    def add_member(self, trip_id, user_id, role):
        from utils.db import db_add_member
        return db_add_member(trip_id, user_id, role)

    def create_invite(self, token, trip_id, created_by, expires_at):
        from utils.db import db_create_invite
        return db_create_invite(token, trip_id, created_by, expires_at)

    def get_invite(self, token):
        from utils.db import db_get_invite
        return db_get_invite(token)


def _repo():
    return _DbRepo()


def _require_user(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required.")
    return user_id


def _frontend_base_url() -> str:
    return os.environ.get("FRONTEND_URL", "https://nnai.app")


class TripCreateRequest(BaseModel):
    title: str = Field(default="", max_length=100)
    destination: dict
    start_date: str | None = None
    end_date: str | None = None


class JoinRequest(BaseModel):
    token: str = Field(min_length=1, max_length=128)


@router.post("")
async def create_trip(req: TripCreateRequest, request: Request):
    user_id = _require_user(request)
    return SVC.create_trip(_repo(), user_id, req.title, req.destination,
                           req.start_date, req.end_date)


@router.get("")
async def list_trips(request: Request):
    user_id = _require_user(request)
    return {"trips": SVC.list_trips(_repo(), user_id)}


@router.get("/{trip_id}")
async def get_trip(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.get_trip_detail(_repo(), trip_id, user_id)
    except SVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except SVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.post("/{trip_id}/invites")
async def create_invite(trip_id: str, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.create_invite(_repo(), trip_id, user_id, _frontend_base_url())
    except SVC.TripNotFound:
        raise HTTPException(status_code=404, detail="Trip not found.")
    except SVC.TripForbidden:
        raise HTTPException(status_code=403, detail="Not a trip member.")


@router.post("/join")
async def join_trip(req: JoinRequest, request: Request):
    user_id = _require_user(request)
    try:
        return SVC.join_trip(_repo(), req.token, user_id)
    except SVC.InviteInvalid:
        raise HTTPException(status_code=400, detail="Invalid invite token.")
    except SVC.InviteExpired:
        raise HTTPException(status_code=410, detail="Invite link has expired.")
```

> NOTE: `@router.post("")`/`@router.get("")` + prefix `/api/trips` → 실제 경로 `/api/trips`. `/join`이 `/{trip_id}`보다 먼저 매칭되도록 라우터 등록 순서상 `/join`·`/{trip_id}/invites`는 구체 경로다. FastAPI는 `/api/trips/join`을 `/{trip_id}`(GET)와 메서드(POST)로 구분하므로 충돌 없음. (join은 POST, get_trip은 GET)

- [ ] **Step 4: server.py 배선** — In `server.py`, add import after `from api.travel import router as travel_router`:

```python
from api.trips import router as trips_router
```

And add include after `app.include_router(travel_router, prefix="/api/travel")`:

```python
app.include_router(trips_router, prefix="/api/trips")
```

- [ ] **Step 5: 통과 확인 + 문법**

Run: `SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_api.py -q`
Expected (로컬): skipped.
Run: `SKIP_EXTERNAL_INIT=1 python3 -c "import ast; ast.parse(open('api/trips.py').read()); ast.parse(open('server.py').read()); print('syntax OK')"`
Expected: `syntax OK`

- [ ] **Step 6: 커밋**

```bash
git add api/trips.py server.py tests/test_trips_api.py
git commit -m "feat(trips): /api/trips 라우터(생성·목록·상세·초대·합류) + server 배선

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 문서 동기화 + CI 등록 + 작업 로그

**Files:**
- Modify: `cowork/backend/db-schema.md`, `cowork/backend/api-reference.md`, `.github/workflows/main-tests.yml`, `tasklist.md`

- [ ] **Step 1: db-schema.md 동기화** — Append a new section to `cowork/backend/db-schema.md` documenting the three tables (`trips`, `trip_members`, `trip_invites`) with columns/types/FK exactly as the DDL in Task 4 Step 1. Use the same table-format the file already uses for existing tables (mirror an existing table's formatting).

- [ ] **Step 2: api-reference.md 동기화** — Append to `cowork/backend/api-reference.md` (and add a 목차 entry) a new section "## Trip & 동행 초대 API (신규)" documenting the 5 endpoints from the 엔드포인트 계약 section above: method, path, request body, response shape, and error codes (401/403/404/410). Mirror the formatting of the existing 여행 추천·일정 API section.

- [ ] **Step 3: CI 등록** — In `.github/workflows/main-tests.yml`, find `tests/test_travel_api.py \` and add after it (preserve indent + trailing ` \`):

```yaml
            tests/test_travel_api.py \
            tests/test_trips_logic.py \
            tests/test_trips_service.py \
            tests/test_trips_api.py \
```

- [ ] **Step 4: 작업 로그** — Append to the END of the most recent date section in `tasklist.md` (create a `## 2026-06-14` heading if not present):

```markdown
## 2026-06-14
- Phase 5(Trip & 동행 초대) 완료: `trips`/`trip_members`/`trip_invites` 테이블(init_db 멱등 DDL) + SQL repo, `api/trips_logic.py`(토큰·만료·권한 순수 헬퍼)·`api/trips_service.py`(orchestration, 주입 repo)·`api/trips.py`(FastAPI 라우터) 신설, `server.py` 배선. `db-schema.md`·`api-reference.md` 동기화.
- 순수 로직/서비스 테스트 22개(로컬 결정론적, 가짜 repo) + 라우터 테스트 6개(CI 전용) + CI 등록. 초대는 만료(14일) 기반 멀티유즈 링크, 합류 멱등. SQL/실DB는 Railway 배포 시 검증.
```

- [ ] **Step 5: 전체 회귀 (로컬)** — Run:
`SKIP_EXTERNAL_INIT=1 python3 -m pytest tests/test_trips_logic.py tests/test_trips_service.py tests/test_trips_api.py -q`
Expected: logic 9 + service 13 + api skipped = **22 passed, (api) skipped**.

- [ ] **Step 6: 커밋**

```bash
git add cowork/backend/db-schema.md cowork/backend/api-reference.md .github/workflows/main-tests.yml tasklist.md
git commit -m "docs(trips): db-schema·api-reference 동기화 + CI 등록 + 작업 로그

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage (Phase 5 = trips/members/invites + 초대 링크 + API):**
- spec `trips`/`trip_members`/`trip_invites` 테이블 → Task 4 DDL ✅ (`trip_plan_items`/`votes`는 Phase 6 — 의도적 제외)
- spec 보고서를 Trip으로 저장(owner=본인) → `POST /api/trips` + `create_trip`(owner 멤버 자동 등록) ✅
- spec 초대 링크 발급 → `POST /api/trips/{id}/invites` + `build_invite_url` ✅
- spec 친구가 링크로 합류(Google 로그인) → `POST /api/trips/join` + `_require_user` 401 게이팅 ✅
- spec 이메일 미발송·링크 기반·실시간 아님 → 링크 토큰만, DB 기반 ✅
- spec 격리(별도 DB) → 멱등 DDL 추가, 기존 테이블 미변경 ✅
- 문서 동기화 규칙 → Task 6 db-schema/api-reference ✅

**2. Placeholder scan:** 코드 step은 전부 실제 코드/명령 포함. Task 6 Step1/2는 "기존 포맷 미러링" 지시(문서 작업 특성상 허용) — 단, 무엇을 문서화할지(테이블/엔드포인트 목록·에러코드)는 구체 명시. ✅

**3. Type consistency:**
- repo 인터페이스 메서드명(create_trip/get_trip/list_trips_for_user/get_member_role/get_members/add_member/create_invite/get_invite)이 FakeRepo·_DbRepo·service 호출에서 모두 일치 ✅
- service 함수 시그니처(`create_trip(repo, owner_user_id, title, destination, start_date, end_date)` 등)가 service 정의·service 테스트·라우터 호출에서 일치 ✅
- `_DbRepo.create_trip`는 trip_id를 내부에서 `L.generate_trip_id()`로 생성해 `db_create_trip(trip_id, ...)` 호출 — db 함수 시그니처(`db_create_trip(trip_id, owner_user_id, title, destination, start_date, end_date)`)와 일치 ✅
- 도메인 예외(TripNotFound/TripForbidden/InviteInvalid/InviteExpired)가 service 정의·service 테스트·라우터 매핑·api 테스트에서 일치, HTTP 매핑(404/403/400/410) 일관 ✅
- 라우터 테스트는 `trips_mod._repo`를 stub하고 `SVC.*`를 monkeypatch → 실제 repo/DB 불필요, CI에서 fastapi로 실행 ✅

**4. 테스트 합계:** logic 9 + service 13(Task2 6 + Task3 7) = 22(로컬). api 6(CI). Phase 5 신규 28. 로컬 회귀 22 passed + api skipped.

**5. 환경 주의(실행자 가이드):** 로컬·CI 모두 Postgres 부재 → Task 4의 SQL은 자동검증 불가, **Railway 배포 시 검증**. `api/trips_logic.py`·`api/trips_service.py`는 psycopg2/fastapi를 import하지 않으므로(서비스는 repo 주입) 로컬 테스트 통과. `_DbRepo`는 utils.db 함수를 **메서드 내부 lazy import** → api/trips.py 모듈 로드시 psycopg2 import 안 됨(라우터 테스트가 CI에서 fastapi만으로 동작). server.py 수정 후 로컬 서버 기동 검증 불필요(fastapi 부재) — ast.parse로 문법 확인.
