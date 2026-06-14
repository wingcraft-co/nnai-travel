"""PostgreSQL 연결 + 스키마 초기화."""
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import Json, RealDictCursor

from utils.crypto import decrypt_text, encrypt_text, has_pii_encryption_key, pii_hash


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")


def _connect_timeout_seconds() -> int:
    raw = os.environ.get("DATABASE_CONNECT_TIMEOUT_SECONDS", "5").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 5


def connect_db(url: str | None = None) -> psycopg2.extensions.connection:
    """DB 연결만 생성한다. 스키마 DDL은 실행하지 않는다."""
    db_url = url or _database_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL 또는 DATABASE_PUBLIC_URL 환경변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(
        db_url,
        connect_timeout=_connect_timeout_seconds(),
    )
    conn.autocommit = False
    return conn


_REQUIRED_SCHEMA_TABLES = {
    "auth_sessions",
    "billing_checkout_sessions",
    "billing_entitlements",
    "billing_provider_events",
    "report_purchases",
    "billing_usage_ledger",
    "dashboard_widget_settings",
    "detail_guide_cache",
    "nomad_journey_stops",
    "onboarding_drafts",
    "rate_limit_hits",
    "tarot_sessions",
    "trip_invites",
    "trip_members",
    "trips",
    "user_city_plans",
    "users",
    "verification_logs",
    "verified_cities",
    "verified_city_external_metrics",
    "verified_city_sources",
    "verified_countries",
    "verified_sources",
    "visits",
}

_REQUIRED_SCHEMA_COLUMNS = {
    "users": {
        "id",
        "email",
        "name",
        "picture",
        "persona_type",
        "created_at",
        "email_enc",
        "email_sha256",
        "name_enc",
        "free_report_city_id",
        "free_report_used_at",
    },
    "billing_entitlements": {
        "user_id",
        "provider",
        "provider_customer_id",
        "provider_subscription_id",
        "plan_code",
        "cancel_at_period_end",
        "grace_until",
        "last_webhook_at",
    },
    "user_city_plans": {
        "city_id",
        "city_kr",
        "city_payload",
        "user_profile",
        "visa_type",
        "visa_expires_at",
        "coworking_space",
        "tax_profile",
        "status",
    },
    "dashboard_widget_settings": {"enabled_widgets", "widget_order", "widget_settings"},
    "detail_guide_cache": {"cache_key", "markdown", "parsed_snapshot", "city_snapshot", "city_id", "is_free"},
    "nomad_journey_stops": {
        "id",
        "user_id",
        "city",
        "country",
        "country_code",
        "lat",
        "lng",
        "note",
        "persona_type",
        "verified_method",
        "supported_city_id",
        "is_supported_city",
        "location_source",
        "line_style",
        "geocode_place_id",
        "geocode_confidence",
        "geocoded_at",
        "gps_verified",
        "flag_color",
        "github_issue_url",
        "github_issue_key",
        "github_issue_status",
        "created_at",
    },
    "onboarding_drafts": {"user_id", "form_draft", "quiz_draft", "updated_at"},
}


def _schema_is_ready(conn: psycopg2.extensions.connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """
        )
        tables = {row[0] for row in cur.fetchall()}
        if not _REQUIRED_SCHEMA_TABLES.issubset(tables):
            conn.rollback()
            return False

        for table, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                """,
                (table,),
            )
            columns = {row[0] for row in cur.fetchall()}
            if not required_columns.issubset(columns):
                conn.rollback()
                return False

    conn.rollback()
    return True


def ensure_database_ready(url: str | None = None) -> None:
    """서버 시작 시 DB가 비어 있거나 구버전일 때만 스키마를 초기화한다."""
    conn = connect_db(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(hashtext(%s))", ("nnai:schema:init",))
        conn.commit()
        if _schema_is_ready(conn):
            return

        initialized = init_db(url)
        initialized.close()
    finally:
        conn.close()


def init_db(url: str | None = None) -> psycopg2.extensions.connection:
    """DB 연결 + 테이블 생성."""
    conn = connect_db(url)
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         TEXT PRIMARY KEY,
                email      TEXT,
                name       TEXT,
                picture    TEXT,
                persona_type TEXT,
                created_at TEXT
            );
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS persona_type TEXT;
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email_enc BYTEA;
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email_sha256 TEXT;
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS name_enc BYTEA;
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS free_report_city_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS free_report_used_at TIMESTAMPTZ;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email_sha256
            ON users(email_sha256);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id      TEXT PRIMARY KEY,
                user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at      TIMESTAMPTZ NOT NULL,
                revoked_at      TIMESTAMPTZ
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
            ON auth_sessions(user_id);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_entitlements (
                user_id                TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                plan_tier              TEXT NOT NULL CHECK (plan_tier IN ('free', 'pro')),
                status                 TEXT NOT NULL CHECK (status IN ('active', 'past_due', 'canceled', 'grace')),
                payg_enabled           BOOLEAN NOT NULL DEFAULT FALSE,
                payg_monthly_cap_usd   NUMERIC(10,2) NOT NULL DEFAULT 50.00,
                current_period_start   TIMESTAMPTZ,
                current_period_end     TIMESTAMPTZ,
                updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS provider TEXT;
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS provider_customer_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS provider_subscription_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS plan_code TEXT NOT NULL DEFAULT 'free';
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE;
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS grace_until TIMESTAMPTZ;
        """)
        cur.execute("""
            ALTER TABLE billing_entitlements
            ADD COLUMN IF NOT EXISTS last_webhook_at TIMESTAMPTZ;
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_usage_ledger (
                id                   BIGSERIAL PRIMARY KEY,
                user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                endpoint             TEXT NOT NULL CHECK (endpoint IN ('recommend', 'detail')),
                request_key          TEXT NOT NULL,
                usage_type           TEXT NOT NULL CHECK (usage_type IN ('subscription', 'payg')),
                estimated_cost_usd   NUMERIC(10,4) NOT NULL DEFAULT 0,
                billed_cost_usd      NUMERIC(10,4),
                created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (request_key)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_provider_events (
                id              BIGSERIAL PRIMARY KEY,
                provider        TEXT NOT NULL,
                event_id        TEXT NOT NULL,
                payload_digest  TEXT NOT NULL,
                processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (provider, event_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS billing_checkout_sessions (
                id                   BIGSERIAL PRIMARY KEY,
                user_id              TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                provider             TEXT NOT NULL,
                provider_checkout_id TEXT UNIQUE,
                plan_code            TEXT NOT NULL,
                status               TEXT NOT NULL CHECK (status IN ('created', 'completed', 'expired', 'failed')),
                return_path          TEXT,
                created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at         TIMESTAMPTZ
            );
        """)
        cur.execute("""
            ALTER TABLE billing_checkout_sessions
            ADD COLUMN IF NOT EXISTS city_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE billing_checkout_sessions
            ADD COLUMN IF NOT EXISTS amount_krw INTEGER;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_billing_checkout_sessions_user_id
            ON billing_checkout_sessions(user_id);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS report_purchases (
                id                  BIGSERIAL PRIMARY KEY,
                user_id             TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                city_id             TEXT NOT NULL,
                provider            TEXT NOT NULL,
                provider_payment_id TEXT NOT NULL,
                amount_krw          INTEGER,
                purchased_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (provider, provider_payment_id),
                UNIQUE (user_id, city_id)
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_report_purchases_user_city
            ON report_purchases(user_id, city_id);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_hits (
                id            BIGSERIAL PRIMARY KEY,
                bucket_key    TEXT NOT NULL,
                window_name   TEXT NOT NULL,
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate_limit_hits_bucket_window_created
            ON rate_limit_hits(bucket_key, window_name, created_at);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tarot_sessions (
                session_id        TEXT PRIMARY KEY,
                cities            JSONB NOT NULL,
                revealed_indices  JSONB,
                created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at        TIMESTAMPTZ NOT NULL
            );
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tarot_sessions_expires_at
            ON tarot_sessions(expires_at);
        """)
        cur.execute("DROP TABLE IF EXISTS pins;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS nomad_journey_stops (
                id              SERIAL PRIMARY KEY,
                user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                city            TEXT NOT NULL,
                country         TEXT NOT NULL,
                country_code    TEXT,
                lat             DOUBLE PRECISION NOT NULL,
                lng             DOUBLE PRECISION NOT NULL,
                note            TEXT NOT NULL CHECK (char_length(note) <= 10),
                persona_type    TEXT,
                verified_method TEXT NOT NULL DEFAULT 'gps_city_confirmed',
                supported_city_id TEXT,
                is_supported_city BOOLEAN NOT NULL DEFAULT FALSE,
                location_source TEXT NOT NULL DEFAULT 'legacy',
                line_style TEXT NOT NULL DEFAULT 'solid',
                geocode_place_id TEXT,
                geocode_confidence DOUBLE PRECISION,
                geocoded_at TIMESTAMPTZ,
                gps_verified BOOLEAN NOT NULL DEFAULT FALSE,
                flag_color TEXT NOT NULL DEFAULT 'red',
                github_issue_url TEXT,
                github_issue_key TEXT,
                github_issue_status TEXT NOT NULL DEFAULT 'not_required',
                CHECK (lat BETWEEN -90 AND 90),
                CHECK (lng BETWEEN -180 AND 180),
                CHECK (line_style IN ('solid', 'dashed')),
                CHECK (flag_color IN ('green', 'red', 'yellow')),
                CHECK (github_issue_status IN ('not_required', 'created', 'linked', 'failed')),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        for column_sql in [
            "ADD COLUMN IF NOT EXISTS supported_city_id TEXT",
            "ADD COLUMN IF NOT EXISTS is_supported_city BOOLEAN NOT NULL DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS location_source TEXT NOT NULL DEFAULT 'legacy'",
            "ADD COLUMN IF NOT EXISTS line_style TEXT NOT NULL DEFAULT 'solid'",
            "ADD COLUMN IF NOT EXISTS geocode_place_id TEXT",
            "ADD COLUMN IF NOT EXISTS geocode_confidence DOUBLE PRECISION",
            "ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMPTZ",
            "ADD COLUMN IF NOT EXISTS gps_verified BOOLEAN NOT NULL DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS flag_color TEXT NOT NULL DEFAULT 'red'",
            "ADD COLUMN IF NOT EXISTS github_issue_url TEXT",
            "ADD COLUMN IF NOT EXISTS github_issue_key TEXT",
            "ADD COLUMN IF NOT EXISTS github_issue_status TEXT NOT NULL DEFAULT 'not_required'",
        ]:
            cur.execute(f"ALTER TABLE nomad_journey_stops {column_sql};")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'chk_nomad_journey_stops_lat_range'
                      AND conrelid = 'nomad_journey_stops'::regclass
                ) THEN
                    ALTER TABLE nomad_journey_stops
                    ADD CONSTRAINT chk_nomad_journey_stops_lat_range CHECK (lat BETWEEN -90 AND 90) NOT VALID;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'chk_nomad_journey_stops_lng_range'
                      AND conrelid = 'nomad_journey_stops'::regclass
                ) THEN
                    ALTER TABLE nomad_journey_stops
                    ADD CONSTRAINT chk_nomad_journey_stops_lng_range CHECK (lng BETWEEN -180 AND 180) NOT VALID;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'chk_nomad_journey_stops_line_style'
                      AND conrelid = 'nomad_journey_stops'::regclass
                ) THEN
                    ALTER TABLE nomad_journey_stops
                    ADD CONSTRAINT chk_nomad_journey_stops_line_style CHECK (line_style IN ('solid', 'dashed')) NOT VALID;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'chk_nomad_journey_stops_flag_color'
                      AND conrelid = 'nomad_journey_stops'::regclass
                ) THEN
                    ALTER TABLE nomad_journey_stops
                    ADD CONSTRAINT chk_nomad_journey_stops_flag_color CHECK (flag_color IN ('green', 'red', 'yellow')) NOT VALID;
                END IF;
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'chk_nomad_journey_stops_github_issue_status'
                      AND conrelid = 'nomad_journey_stops'::regclass
                ) THEN
                    ALTER TABLE nomad_journey_stops
                    ADD CONSTRAINT chk_nomad_journey_stops_github_issue_status CHECK (github_issue_status IN ('not_required', 'created', 'linked', 'failed')) NOT VALID;
                END IF;
            END $$;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_user_created
            ON nomad_journey_stops(user_id, created_at);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_city
            ON nomad_journey_stops(city, country);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_nomad_journey_stops_persona
            ON nomad_journey_stops(persona_type);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                path       TEXT PRIMARY KEY,
                count      BIGINT NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_city_plans (
                id               BIGSERIAL PRIMARY KEY,
                user_id          TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                city_id          TEXT,
                city             TEXT NOT NULL,
                city_kr          TEXT,
                country          TEXT,
                country_id       TEXT,
                city_payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
                user_profile     JSONB NOT NULL DEFAULT '{}'::jsonb,
                arrived_at       TEXT,
                visa_type        TEXT NOT NULL DEFAULT '관광비자',
                visa_expires_at  TEXT,
                coworking_space  JSONB NOT NULL DEFAULT '{}'::jsonb,
                tax_profile      JSONB NOT NULL DEFAULT '{}'::jsonb,
                status           TEXT NOT NULL DEFAULT 'active'
                                 CHECK (status IN ('active', 'archived')),
                created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS city_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS city_kr TEXT;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS city_payload JSONB NOT NULL DEFAULT '{}'::jsonb;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS user_profile JSONB NOT NULL DEFAULT '{}'::jsonb;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS visa_type TEXT NOT NULL DEFAULT '관광비자';
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS visa_expires_at TEXT;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS coworking_space JSONB NOT NULL DEFAULT '{}'::jsonb;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS tax_profile JSONB NOT NULL DEFAULT '{}'::jsonb;
        """)
        cur.execute("""
            ALTER TABLE user_city_plans
            ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active';
        """)
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_city_plans_one_active
            ON user_city_plans(user_id)
            WHERE status = 'active';
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_widget_settings (
                user_id          TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                enabled_widgets  JSONB NOT NULL DEFAULT '[]'::jsonb,
                widget_order     JSONB NOT NULL DEFAULT '[]'::jsonb,
                widget_settings  JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS onboarding_drafts (
                user_id      TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                form_draft   JSONB,
                quiz_draft   JSONB,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS detail_guide_cache (
                id              BIGSERIAL PRIMARY KEY,
                user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                cache_key       TEXT NOT NULL,
                markdown        TEXT NOT NULL,
                parsed_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
                city_snapshot   JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, cache_key)
            );
        """)
        cur.execute("""
            ALTER TABLE detail_guide_cache
            ADD COLUMN IF NOT EXISTS city_id TEXT;
        """)
        cur.execute("""
            ALTER TABLE detail_guide_cache
            ADD COLUMN IF NOT EXISTS is_free BOOLEAN NOT NULL DEFAULT FALSE;
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_detail_guide_cache_user_city
            ON detail_guide_cache(user_id, city_id);
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_sources (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                publisher     TEXT,
                url           TEXT NOT NULL,
                metric_scope  JSONB NOT NULL DEFAULT '[]'::jsonb,
                last_checked  TEXT,
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_countries (
                country_id                 TEXT PRIMARY KEY,
                name                       TEXT NOT NULL,
                name_kr                    TEXT,
                visa_type                  TEXT NOT NULL,
                min_income_usd             DOUBLE PRECISION,
                stay_months                INTEGER,
                renewable                  BOOLEAN,
                visa_fee_usd               DOUBLE PRECISION,
                source_url                 TEXT,
                data_verified_date         TEXT,
                is_verified                BOOLEAN NOT NULL DEFAULT TRUE,
                raw_data                   JSONB NOT NULL,
                updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_cities (
                city_id                    TEXT PRIMARY KEY,
                city                       TEXT NOT NULL,
                city_kr                    TEXT,
                country                    TEXT,
                country_id                 TEXT NOT NULL,
                monthly_cost_usd           DOUBLE PRECISION,
                internet_mbps              DOUBLE PRECISION,
                safety_score               DOUBLE PRECISION,
                english_score              DOUBLE PRECISION,
                nomad_score                DOUBLE PRECISION,
                tax_residency_days         INTEGER,
                data_verified_date         TEXT,
                is_verified                BOOLEAN NOT NULL DEFAULT TRUE,
                raw_data                   JSONB NOT NULL,
                updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_city_sources (
                city_id       TEXT NOT NULL REFERENCES verified_cities(city_id) ON DELETE CASCADE,
                source_id     TEXT NOT NULL REFERENCES verified_sources(id) ON DELETE CASCADE,
                linked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (city_id, source_id)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verification_logs (
                id            BIGSERIAL PRIMARY KEY,
                entity_type   TEXT NOT NULL,
                entity_id     TEXT NOT NULL,
                action        TEXT NOT NULL,
                source_id     TEXT,
                verified_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                notes         TEXT,
                payload       JSONB NOT NULL DEFAULT '{}'::jsonb
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS verified_city_external_metrics (
                id            BIGSERIAL PRIMARY KEY,
                city_id       TEXT NOT NULL,
                source_id     TEXT NOT NULL,
                metric_key    TEXT NOT NULL,
                metric_value  DOUBLE PRECISION,
                fetched_at    TEXT,
                payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (city_id, source_id, metric_key)
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verified_cities_country_id ON verified_cities(country_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verification_logs_entity ON verification_logs(entity_type, entity_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verified_city_external_metrics_city_id ON verified_city_external_metrics(city_id);")
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
    backfill_legacy_user_identity(conn)
    conn.commit()
    return conn


_lock = threading.Lock()
_billing_lock = threading.Lock()
_rate_limit_lock = threading.Lock()
_thread_local = threading.local()


def release_thread_connection_transaction() -> None:
    """요청 종료 후 스레드 로컬 연결에 남은 트랜잭션을 정리한다."""
    conn = getattr(_thread_local, "conn", None)
    if conn is None or conn.closed:
        return

    try:
        if conn.get_transaction_status() != psycopg2.extensions.TRANSACTION_STATUS_IDLE:
            conn.rollback()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def get_conn() -> psycopg2.extensions.connection:
    """현재 스레드에서 재사용할 DB 연결 반환."""
    with _lock:
        conn = getattr(_thread_local, "conn", None)
        if conn is None or conn.closed:
            conn = connect_db()
            _thread_local.conn = conn
            return conn

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except psycopg2.Error:
            try:
                conn.rollback()
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = connect_db()
                _thread_local.conn = conn
    return conn


def backfill_legacy_user_identity(
    conn: psycopg2.extensions.connection | None = None,
) -> int:
    resolved_conn = conn or get_conn()
    if not has_pii_encryption_key():
        return 0
    migrated = 0
    with resolved_conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, name
            FROM users
            WHERE email IS NOT NULL
              AND email <> ''
            """
        )
        rows = cur.fetchall()
        for user_id, email, name in rows:
            cur.execute(
                """
                UPDATE users
                SET email = NULL,
                    name = NULL,
                    email_enc = COALESCE(email_enc, %s),
                    email_sha256 = COALESCE(email_sha256, %s),
                    name_enc = COALESCE(name_enc, %s)
                WHERE id = %s
                """,
                (
                    encrypt_text(email),
                    pii_hash(email),
                    encrypt_text(name),
                    user_id,
                ),
            )
            migrated += 1

    if conn is None:
        resolved_conn.commit()

    return migrated


def get_billing_entitlement(user_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT plan_tier, status, payg_enabled, payg_monthly_cap_usd,
                   current_period_start, current_period_end,
                   provider, provider_customer_id, provider_subscription_id,
                   plan_code, cancel_at_period_end, grace_until, last_webhook_at
            FROM billing_entitlements
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    return {
        "plan_tier": row[0],
        "status": row[1],
        "payg_enabled": row[2],
        "payg_monthly_cap_usd": float(row[3]),
        "current_period_start": row[4],
        "current_period_end": row[5],
        "provider": row[6],
        "provider_customer_id": row[7],
        "provider_subscription_id": row[8],
        "plan_code": row[9],
        "cancel_at_period_end": row[10],
        "grace_until": row[11],
        "last_webhook_at": row[12],
    }


_DEFAULT_DASHBOARD_WIDGETS = [
    "weather",
    "exchange",
    "stay",
    "visa",
    "action_plan",
    "coworking",
    "tax",
    "disaster",
    "budget",
    "housing",
    "insurance",
    "local_events",
]


def _serialize_city_plan(row: tuple | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row[0],
        "city_id": row[1],
        "city": row[2],
        "city_kr": row[3],
        "country": row[4],
        "country_id": row[5],
        "city_payload": row[6] or {},
        "user_profile": row[7] or {},
        "arrived_at": row[8],
        "visa_type": row[9],
        "visa_expires_at": row[10],
        "coworking_space": row[11] or {},
        "tax_profile": row[12] or {},
        "status": row[13],
        "created_at": str(row[14]),
        "updated_at": str(row[15]),
    }


def _serialize_dashboard_widgets(row: tuple | None) -> dict:
    if row is None:
        return {
            "enabled_widgets": _DEFAULT_DASHBOARD_WIDGETS,
            "widget_order": _DEFAULT_DASHBOARD_WIDGETS,
            "widget_settings": {},
            "updated_at": None,
        }
    return {
        "enabled_widgets": row[0] or _DEFAULT_DASHBOARD_WIDGETS,
        "widget_order": row[1] or _DEFAULT_DASHBOARD_WIDGETS,
        "widget_settings": row[2] or {},
        "updated_at": str(row[3]),
    }


def get_active_user_city_plan(user_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, city_id, city, city_kr, country, country_id,
                   city_payload, user_profile, arrived_at, visa_type, visa_expires_at,
                   coworking_space, tax_profile, status, created_at, updated_at
            FROM user_city_plans
            WHERE user_id = %s AND status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return _serialize_city_plan(row)


def confirm_user_city_plan(
    *,
    user_id: str,
    city_payload: dict,
    user_profile: dict | None = None,
    arrived_at: str | None = None,
) -> dict:
    conn = get_conn()
    city = str(city_payload.get("city") or city_payload.get("city_kr") or "Unknown city")
    city_kr = city_payload.get("city_kr")
    country = city_payload.get("country")
    country_id = city_payload.get("country_id")
    city_id = city_payload.get("id") or city_payload.get("city_id")
    visa_type = "관광비자"
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE user_city_plans
            SET status = 'archived',
                updated_at = NOW()
            WHERE user_id = %s AND status = 'active'
            """,
            (user_id,),
        )
        cur.execute(
            """
            INSERT INTO user_city_plans (
                user_id, city_id, city, city_kr, country, country_id,
                city_payload, user_profile, arrived_at, visa_type
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            RETURNING id, city_id, city, city_kr, country, country_id,
                      city_payload, user_profile, arrived_at, visa_type, visa_expires_at,
                      coworking_space, tax_profile, status, created_at, updated_at
            """,
            (
                user_id,
                city_id,
                city,
                city_kr,
                country,
                country_id,
                Json(city_payload),
                Json(user_profile or {}),
                arrived_at,
                visa_type,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_city_plan(row)


def update_user_city_plan(
    *,
    user_id: str,
    arrived_at: str | None = None,
    visa_type: str | None = None,
    visa_expires_at: str | None = None,
    coworking_space: dict | None = None,
    tax_profile: dict | None = None,
) -> dict | None:
    assignments = []
    values = []
    if arrived_at is not None:
        assignments.append("arrived_at = %s")
        values.append(arrived_at)
    if visa_type is not None:
        assignments.append("visa_type = %s")
        values.append(visa_type)
    if visa_expires_at is not None:
        assignments.append("visa_expires_at = %s")
        values.append(visa_expires_at)
    if coworking_space is not None:
        assignments.append("coworking_space = %s")
        values.append(Json(coworking_space))
    if tax_profile is not None:
        assignments.append("tax_profile = %s")
        values.append(Json(tax_profile))
    if not assignments:
        return get_active_user_city_plan(user_id)

    values.append(user_id)
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE user_city_plans
            SET {", ".join(assignments)},
                updated_at = NOW()
            WHERE user_id = %s AND status = 'active'
            RETURNING id, city_id, city, city_kr, country, country_id,
                      city_payload, user_profile, arrived_at, visa_type, visa_expires_at,
                      coworking_space, tax_profile, status, created_at, updated_at
            """,
            tuple(values),
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_city_plan(row)


def get_or_create_dashboard_widget_settings(user_id: str) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dashboard_widget_settings (
                user_id, enabled_widgets, widget_order, widget_settings
            ) VALUES (%s, %s, %s, '{}'::jsonb)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, Json(_DEFAULT_DASHBOARD_WIDGETS), Json(_DEFAULT_DASHBOARD_WIDGETS)),
        )
        cur.execute(
            """
            SELECT enabled_widgets, widget_order, widget_settings, updated_at
            FROM dashboard_widget_settings
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_dashboard_widgets(row)


def update_dashboard_widget_settings(
    *,
    user_id: str,
    enabled_widgets: list[str],
    widget_order: list[str],
    widget_settings: dict,
) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO dashboard_widget_settings (
                user_id, enabled_widgets, widget_order, widget_settings, updated_at
            ) VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                enabled_widgets = EXCLUDED.enabled_widgets,
                widget_order = EXCLUDED.widget_order,
                widget_settings = EXCLUDED.widget_settings,
                updated_at = NOW()
            RETURNING enabled_widgets, widget_order, widget_settings, updated_at
            """,
            (user_id, Json(enabled_widgets), Json(widget_order), Json(widget_settings)),
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_dashboard_widgets(row)


def _serialize_onboarding_draft(row: tuple | None) -> dict:
    if row is None:
        return {
            "form_draft": None,
            "quiz_draft": None,
            "updated_at": None,
        }
    return {
        "form_draft": row[0],
        "quiz_draft": row[1],
        "updated_at": str(row[2]),
    }


def get_onboarding_draft(user_id: str) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT form_draft, quiz_draft, updated_at
            FROM onboarding_drafts
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return _serialize_onboarding_draft(row)


def upsert_onboarding_draft(
    *,
    user_id: str,
    form_draft: dict | None,
    quiz_draft: dict | None,
) -> dict:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO onboarding_drafts (
                user_id, form_draft, quiz_draft, updated_at
            ) VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                form_draft = EXCLUDED.form_draft,
                quiz_draft = EXCLUDED.quiz_draft,
                updated_at = NOW()
            RETURNING form_draft, quiz_draft, updated_at
            """,
            (user_id, Json(form_draft), Json(quiz_draft)),
        )
        row = cur.fetchone()
    conn.commit()
    return _serialize_onboarding_draft(row)


def _selected_city_snapshot(parsed_data: dict, city_index: int) -> dict:
    top_cities = parsed_data.get("top_cities")
    if not isinstance(top_cities, list) or not top_cities:
        return {}
    if city_index < 0 or city_index >= len(top_cities):
        city_index = 0
    city = top_cities[city_index]
    return city if isinstance(city, dict) else {}


def get_detail_guide_cache(user_id: str, cache_key: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, markdown, parsed_snapshot, city_snapshot, created_at, updated_at
            FROM detail_guide_cache
            WHERE user_id = %s AND cache_key = %s
            """,
            (user_id, cache_key),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "markdown": row[1],
        "parsed_snapshot": row[2] or {},
        "city_snapshot": row[3] or {},
        "created_at": str(row[4]),
        "updated_at": str(row[5]),
    }


def count_detail_guide_cache_entries(user_id: str) -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM detail_guide_cache
            WHERE user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    return int(row[0] or 0)


def list_detail_guide_cache_entries(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    safe_limit = max(1, min(limit, 100))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, markdown, parsed_snapshot, city_snapshot,
                   city_id, is_free, created_at, updated_at
            FROM detail_guide_cache
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (user_id, safe_limit),
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "markdown": row[1],
            "parsed_snapshot": row[2] or {},
            "city_snapshot": row[3] or {},
            "city_id": row[4],
            "is_free": bool(row[5]) if row[5] is not None else False,
            "created_at": str(row[6]),
            "updated_at": str(row[7]),
        }
        for row in rows
    ]


def get_detail_guide_by_city_id(user_id: str, city_id: str) -> dict | None:
    """단건 결제 모델: city_id로 보고서 1개 조회. is_free=false 우선 (결제분 우선)."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, markdown, parsed_snapshot, city_snapshot,
                   city_id, is_free, cache_key, created_at, updated_at
            FROM detail_guide_cache
            WHERE user_id = %s AND city_id = %s
            ORDER BY is_free ASC, updated_at DESC
            LIMIT 1
            """,
            (user_id, city_id),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "markdown": row[1],
        "parsed_snapshot": row[2] or {},
        "city_snapshot": row[3] or {},
        "city_id": row[4],
        "is_free": bool(row[5]) if row[5] is not None else False,
        "cache_key": row[6],
        "created_at": str(row[7]),
        "updated_at": str(row[8]),
    }


def save_detail_guide_cache(
    *,
    user_id: str,
    cache_key: str,
    markdown: str,
    parsed_data: dict,
    city_index: int,
    city_id: str | None = None,
    is_free: bool = False,
) -> dict:
    conn = get_conn()
    city_snapshot = _selected_city_snapshot(parsed_data, city_index)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO detail_guide_cache (
                user_id, cache_key, markdown, parsed_snapshot, city_snapshot,
                city_id, is_free, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, cache_key) DO UPDATE SET
                markdown = EXCLUDED.markdown,
                parsed_snapshot = EXCLUDED.parsed_snapshot,
                city_snapshot = EXCLUDED.city_snapshot,
                city_id = COALESCE(EXCLUDED.city_id, detail_guide_cache.city_id),
                -- 결제 완료 (is_free=false)는 무료 (is_free=true)로 다운그레이드되지 않음
                is_free = detail_guide_cache.is_free AND EXCLUDED.is_free,
                updated_at = NOW()
            RETURNING id, markdown, parsed_snapshot, city_snapshot, city_id, is_free, created_at, updated_at
            """,
            (
                user_id,
                cache_key,
                markdown,
                Json(parsed_data),
                Json(city_snapshot),
                city_id,
                is_free,
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return {
        "id": row[0],
        "markdown": row[1],
        "parsed_snapshot": row[2] or {},
        "city_snapshot": row[3] or {},
        "city_id": row[4],
        "is_free": bool(row[5]) if row[5] is not None else False,
        "created_at": str(row[6]),
        "updated_at": str(row[7]),
    }


# ── 무료 보고서 1회 권한 추적 ───────────────────────────────────────

def get_user_free_report_city_id(user_id: str) -> str | None:
    """사용자가 무료로 받은 도시 id를 반환. NULL이면 아직 미사용."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT free_report_city_id FROM users WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    return row[0] if row and row[0] else None


def claim_free_report_city(user_id: str, city_id: str) -> bool:
    """무료 보고서를 city_id로 부여. 이미 다른 도시에 부여됐으면 False, 새로 부여하면 True."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET free_report_city_id = %s,
                free_report_used_at = NOW()
            WHERE id = %s
              AND (free_report_city_id IS NULL OR free_report_city_id = %s)
            RETURNING free_report_city_id
            """,
            (city_id, user_id, city_id),
        )
        row = cur.fetchone()
    conn.commit()
    return row is not None and row[0] == city_id


def mark_report_purchased(user_id: str, city_id: str) -> None:
    """결제 완료 시 호출. 해당 city_id의 is_free=true 행을 false로 업그레이드."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE detail_guide_cache
            SET is_free = FALSE, updated_at = NOW()
            WHERE user_id = %s AND city_id = %s AND is_free = TRUE
            """,
            (user_id, city_id),
        )
    conn.commit()


def list_user_owned_city_ids(user_id: str) -> list[dict]:
    """사용자가 보유한 city_id 목록 (free/purchased 모두). /auth/me 응답용."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT city_id,
                   bool_and(is_free) AS only_free  -- 모두 무료면 true (결제분 있으면 false)
            FROM detail_guide_cache
            WHERE user_id = %s AND city_id IS NOT NULL
            GROUP BY city_id
            ORDER BY MAX(updated_at) DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    return [{"city_id": row[0], "is_free": bool(row[1])} for row in rows]


def upsert_billing_entitlement(
    user_id: str,
    *,
    provider: str,
    plan_tier: str,
    plan_code: str,
    status: str,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    current_period_start,
    current_period_end,
    cancel_at_period_end: bool = False,
    grace_until=None,
) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO billing_entitlements (
                user_id, provider, plan_tier, plan_code, status,
                provider_customer_id, provider_subscription_id,
                current_period_start, current_period_end,
                cancel_at_period_end, grace_until, updated_at, last_webhook_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, NOW(), NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                provider = EXCLUDED.provider,
                plan_tier = EXCLUDED.plan_tier,
                plan_code = EXCLUDED.plan_code,
                status = EXCLUDED.status,
                provider_customer_id = COALESCE(EXCLUDED.provider_customer_id, billing_entitlements.provider_customer_id),
                provider_subscription_id = COALESCE(EXCLUDED.provider_subscription_id, billing_entitlements.provider_subscription_id),
                current_period_start = COALESCE(EXCLUDED.current_period_start, billing_entitlements.current_period_start),
                current_period_end = COALESCE(EXCLUDED.current_period_end, billing_entitlements.current_period_end),
                cancel_at_period_end = EXCLUDED.cancel_at_period_end,
                grace_until = EXCLUDED.grace_until,
                updated_at = NOW(),
                last_webhook_at = NOW()
            """,
            (
                user_id,
                provider,
                plan_tier,
                plan_code,
                status,
                provider_customer_id,
                provider_subscription_id,
                current_period_start,
                current_period_end,
                cancel_at_period_end,
                grace_until,
            ),
        )
    conn.commit()


def persist_billing_checkout_session(
    *,
    user_id: str,
    provider_checkout_id: str | None,
    plan_code: str,
    return_path: str | None,
    status: str,
    provider: str = "polar",
    city_id: str | None = None,
    amount_krw: int | None = None,
) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO billing_checkout_sessions (
                user_id, provider, provider_checkout_id, plan_code,
                city_id, amount_krw, status, return_path
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (provider_checkout_id) DO UPDATE SET
                city_id = COALESCE(EXCLUDED.city_id, billing_checkout_sessions.city_id),
                amount_krw = COALESCE(EXCLUDED.amount_krw, billing_checkout_sessions.amount_krw),
                status = EXCLUDED.status,
                return_path = EXCLUDED.return_path
            """,
            (user_id, provider, provider_checkout_id, plan_code, city_id, amount_krw, status, return_path),
        )
    conn.commit()


def get_billing_checkout_session(provider_checkout_id: str | None) -> dict | None:
    if not provider_checkout_id:
        return None

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id, provider, provider_checkout_id, plan_code,
                   city_id, amount_krw, status, return_path, completed_at
            FROM billing_checkout_sessions
            WHERE provider_checkout_id = %s
            """,
            (provider_checkout_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "user_id": row[0],
        "provider": row[1],
        "provider_checkout_id": row[2],
        "plan_code": row[3],
        "city_id": row[4],
        "amount_krw": row[5],
        "status": row[6],
        "return_path": row[7],
        "completed_at": row[8],
    }


def mark_checkout_session_status(
    provider_checkout_id: str | None,
    status: str,
) -> None:
    if not provider_checkout_id:
        return

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE billing_checkout_sessions
            SET status = %s,
                completed_at = CASE
                    WHEN %s = 'completed' THEN NOW()
                    ELSE completed_at
                END
            WHERE provider_checkout_id = %s
            """,
            (status, status, provider_checkout_id),
        )
    conn.commit()


def record_report_purchase(
    *,
    user_id: str,
    city_id: str,
    provider: str,
    provider_payment_id: str,
    amount_krw: int | None,
) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO report_purchases (
                user_id, city_id, provider, provider_payment_id, amount_krw
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id, city_id) DO UPDATE SET
                provider = EXCLUDED.provider,
                provider_payment_id = EXCLUDED.provider_payment_id,
                amount_krw = EXCLUDED.amount_krw,
                purchased_at = NOW()
            """,
            (user_id, city_id, provider, provider_payment_id, amount_krw),
        )
    conn.commit()


def user_has_report_purchase(user_id: str, city_id: str) -> bool:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM report_purchases
            WHERE user_id = %s AND city_id = %s
            LIMIT 1
            """,
            (user_id, city_id),
        )
        row = cur.fetchone()
    return row is not None


def record_billing_provider_event(
    *,
    provider: str,
    event_id: str,
    payload_digest: str,
) -> bool:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO billing_provider_events (provider, event_id, payload_digest)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, event_id) DO NOTHING
            """,
            (provider, event_id, payload_digest),
        )
        inserted = cur.rowcount > 0
    conn.commit()
    return inserted


def upsert_user_identity(
    user_id: str,
    *,
    email: str | None,
    name: str | None,
    picture: str | None,
    created_at: str | None = None,
) -> None:
    conn = get_conn()
    use_encrypted_pii = has_pii_encryption_key()
    email_enc = encrypt_text(email)
    name_enc = encrypt_text(name)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (
                id, email, name, picture, email_enc, email_sha256, name_enc, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(id) DO UPDATE SET
                email = EXCLUDED.email,
                name = EXCLUDED.name,
                picture = EXCLUDED.picture,
                email_enc = EXCLUDED.email_enc,
                email_sha256 = EXCLUDED.email_sha256,
                name_enc = EXCLUDED.name_enc
            """,
            (
                user_id,
                None if use_encrypted_pii else email,
                None if use_encrypted_pii else name,
                picture,
                email_enc,
                pii_hash(email),
                name_enc,
                created_at or datetime.now(timezone.utc).isoformat(),
            ),
        )
    conn.commit()


def get_user_identity(user_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, email, email_enc, name, name_enc, picture, persona_type
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    email = decrypt_text(row[2]) or row[1]
    name = decrypt_text(row[4]) or row[3]
    return {
        "id": row[0],
        "email": email,
        "name": name,
        "picture": row[5],
        "persona_type": row[6],
    }


def create_auth_session(
    user_id: str,
    *,
    session_id: str | None = None,
    ttl_seconds: int = 86400,
) -> str:
    conn = get_conn()
    resolved_session_id = session_id or secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth_sessions (session_id, user_id, expires_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                expires_at = EXCLUDED.expires_at,
                revoked_at = NULL
            """,
            (resolved_session_id, user_id, expires_at),
        )
    conn.commit()
    return resolved_session_id


def get_auth_session_identity(session_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT user_id
            FROM auth_sessions
            WHERE session_id = %s
              AND revoked_at IS NULL
              AND expires_at > NOW()
            """,
            (session_id,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    identity = get_user_identity(row[0])
    if identity is None:
        return None

    return {
        "uid": identity["id"],
        "name": identity["name"],
        "picture": identity["picture"],
        "email": identity["email"],
        "persona_type": identity["persona_type"],
    }


def revoke_auth_session(session_id: str) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = NOW()
            WHERE session_id = %s
              AND revoked_at IS NULL
            """,
            (session_id,),
        )
    conn.commit()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def sum_payg_usage(user_id: str, period_start: datetime | None, period_end: datetime | None) -> float:
    conn = get_conn()
    start = period_start or datetime.min.replace(tzinfo=timezone.utc)
    end = period_end or datetime.max.replace(tzinfo=timezone.utc)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(COALESCE(billed_cost_usd, estimated_cost_usd)), 0)
            FROM billing_usage_ledger
            WHERE user_id = %s
              AND usage_type = 'payg'
              AND created_at >= %s
              AND created_at < %s
            """,
            (user_id, start, end),
        )
        row = cur.fetchone()
    return float(row[0] or 0.0)


def reserve_payg_usage(
    user_id: str,
    endpoint: str,
    request_key: str,
    estimated_cost_usd: float,
    period_start: datetime | None,
    period_end: datetime | None,
    monthly_cap_usd: float,
) -> float:
    conn = get_conn()
    start = period_start or _utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = period_end or datetime.max.replace(tzinfo=timezone.utc)

    with _billing_lock:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"payg:{user_id}",))
            cur.execute(
                """
                SELECT COALESCE(SUM(COALESCE(billed_cost_usd, estimated_cost_usd)), 0)
                FROM billing_usage_ledger
                WHERE user_id = %s
                  AND usage_type = 'payg'
                  AND created_at >= %s
                  AND created_at < %s
                """,
                (user_id, start, end),
            )
            current_usage = float(cur.fetchone()[0] or 0.0)
            if current_usage + estimated_cost_usd > monthly_cap_usd:
                conn.rollback()
                return current_usage

            cur.execute(
                """
                INSERT INTO billing_usage_ledger (
                    user_id, endpoint, request_key, usage_type, estimated_cost_usd
                ) VALUES (%s, %s, %s, 'payg', %s)
                ON CONFLICT (request_key) DO NOTHING
                """,
                (user_id, endpoint, request_key, estimated_cost_usd),
            )
        conn.commit()
    return -1.0


def release_usage_reservation(request_key: str) -> None:
    conn = get_conn()
    with _billing_lock:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM billing_usage_ledger WHERE request_key = %s", (request_key,))
        conn.commit()


def consume_rate_limit_token(
    bucket_key: str,
    window_name: str,
    window_seconds: int,
    limit: int,
) -> bool:
    conn = get_conn()
    with _rate_limit_lock:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"rl:{bucket_key}:{window_name}",))
            cur.execute(
                """
                DELETE FROM rate_limit_hits
                WHERE bucket_key = %s
                  AND window_name = %s
                  AND created_at < NOW() - make_interval(secs => %s)
                """,
                (bucket_key, window_name, window_seconds),
            )
            cur.execute(
                """
                SELECT COUNT(*)
                FROM rate_limit_hits
                WHERE bucket_key = %s
                  AND window_name = %s
                  AND created_at >= NOW() - make_interval(secs => %s)
                """,
                (bucket_key, window_name, window_seconds),
            )
            current_count = int(cur.fetchone()[0] or 0)
            if current_count >= limit:
                conn.rollback()
                return False

            cur.execute(
                """
                INSERT INTO rate_limit_hits (bucket_key, window_name)
                VALUES (%s, %s)
                """,
                (bucket_key, window_name),
            )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Trip / Invite SQL repo functions
# ---------------------------------------------------------------------------

def db_create_trip(trip_id: str, owner_user_id: str, title: str, destination: dict, start_date, end_date) -> dict:
    """trips 행 + owner trip_members 행을 단일 트랜잭션으로 삽입(orphan trip 방지) 후 trip dict 반환."""
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
        cur.execute(
            "INSERT INTO trip_members (trip_id, user_id, role) VALUES (%s, %s, 'owner') "
            "ON CONFLICT (trip_id, user_id) DO NOTHING;",
            (trip_id, owner_user_id),
        )
    conn.commit()
    return dict(row)


def db_get_trip(trip_id: str) -> dict | None:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, owner_user_id, title, destination, start_date, end_date, created_at "
            "FROM trips WHERE id = %s;",
            (trip_id,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def db_list_trips_for_user(user_id: str) -> list[dict]:
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


def db_get_member_role(trip_id: str, user_id: str) -> str | None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT role FROM trip_members WHERE trip_id = %s AND user_id = %s;",
            (trip_id, user_id),
        )
        row = cur.fetchone()
    return row[0] if row else None


def db_get_members(trip_id: str) -> list[dict]:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT user_id, role, joined_at FROM trip_members "
            "WHERE trip_id = %s ORDER BY joined_at;",
            (trip_id,),
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def db_add_member(trip_id: str, user_id: str, role: str) -> None:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO trip_members (trip_id, user_id, role) VALUES (%s, %s, %s) "
            "ON CONFLICT (trip_id, user_id) DO NOTHING;",
            (trip_id, user_id, role),
        )
    conn.commit()


def db_create_invite(token: str, trip_id: str, created_by: str, expires_at) -> dict:
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


def db_get_invite(token: str) -> dict | None:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT token, trip_id, created_by, expires_at, created_at "
            "FROM trip_invites WHERE token = %s;",
            (token,),
        )
        row = cur.fetchone()
    return dict(row) if row else None
