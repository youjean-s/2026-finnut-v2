import os
import sqlite3
from datetime import datetime

# DB 경로 통일 (루트/data/kosaf_scholarships.db)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "kosaf_scholarships.db")


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # =========================================================
    # 1) scholarships 테이블 (legacy 유지)
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scholarships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_key TEXT,
            name TEXT,
            type TEXT,
            period TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT,
            link TEXT,
            condition TEXT,
            grant TEXT,
            raw_json TEXT,
            source_uddi TEXT,
            fetched_at TEXT
        );
    """)

    needed_cols = {
        "policy_key": "TEXT",
        "source_uddi": "TEXT",
        "fetched_at": "TEXT",
    }
    for col, col_type in needed_cols.items():
        if not _column_exists(conn, "scholarships", col):
            cur.execute(f"ALTER TABLE scholarships ADD COLUMN {col} {col_type};")

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_scholarships_policy_key
        ON scholarships(policy_key);
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_status ON scholarships(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_name ON scholarships(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_scholarships_type ON scholarships(type);")

    # =========================================================
    # 2) policies 테이블
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_key TEXT UNIQUE,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            provider TEXT,
            period TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT,
            link TEXT,
            condition TEXT,
            benefit TEXT,
            source TEXT,
            source_id TEXT,
            fetched_at TEXT,
            source_meta TEXT,   -- 수집 소스별 구조화 메타 (JSON). KOSAF=NULL, 온통청년=JSON
            raw_json TEXT
        );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS ix_policies_category ON policies(category);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_policies_status ON policies(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_policies_name ON policies(name);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_policies_provider ON policies(provider);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_policies_source ON policies(source);")

    # 기존 DB 마이그레이션: source_meta 컬럼 없으면 추가
    if not _column_exists(conn, "policies", "source_meta"):
        cur.execute("ALTER TABLE policies ADD COLUMN source_meta TEXT;")
        print("[db] policies.source_meta 컬럼 추가 완료 (마이그레이션)")

    # =========================================================
    # 3) users 테이블
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT,
            gender TEXT,
            birthdate TEXT,          -- YYYY-MM-DD (나이는 생년월일로 자동 계산)
            income_level INTEGER,    -- 소득분위 1~10
            region TEXT,
            school TEXT,             -- 대학생 | 대학원생 | 기타
            student INTEGER,         -- 0/1
            keywords_json TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)

    # 기존 DB 마이그레이션: 컬럼 없으면 추가
    migration_cols = {
        "nickname": "TEXT",
        "gender": "TEXT",
        "birthdate": "TEXT",
        "income_level": "INTEGER",
        "school": "TEXT",
    }
    for col, col_type in migration_cols.items():
        if not _column_exists(conn, "users", col):
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type};")
            print(f"[db] users.{col} 컬럼 추가 완료 (마이그레이션)")

    # category_preference 제거는 SQLite가 DROP COLUMN 미지원이라 그냥 둠
    cur.execute("CREATE INDEX IF NOT EXISTS ix_users_region ON users(region);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_users_school ON users(school);")

    # =========================================================
    # 4) policy_eligibility 테이블
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS policy_eligibility (
            policy_id INTEGER PRIMARY KEY,
            min_age INTEGER,
            max_age INTEGER,
            region TEXT,
            student_required INTEGER,
            income_type TEXT,
            income_max_percent INTEGER,
            income_max_quintile INTEGER,
            keywords_json TEXT,
            evidence_json TEXT,
            updated_at TEXT,
            FOREIGN KEY(policy_id) REFERENCES policies(id) ON DELETE CASCADE
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_elig_region ON policy_eligibility(region);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_elig_age ON policy_eligibility(min_age, max_age);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_elig_student ON policy_eligibility(student_required);")

    # =========================================================
    # 5) mission_logs / mission_executions 테이블 (미션 실행 로그)
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mission_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_title TEXT NOT NULL,
            card_mission TEXT NOT NULL,   -- 코칭카드 원문 미션 문구
            category TEXT NOT NULL,       -- convenience/cafe/food/... (fhi.py VALID_CATEGORIES 재사용)
            target_count INTEGER NOT NULL,
            current_count INTEGER DEFAULT 0,
            period_start TEXT NOT NULL,   -- ISO date
            period_end TEXT NOT NULL,     -- ISO date
            status TEXT DEFAULT 'active', -- active / completed / failed
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mission_logs_user ON mission_logs(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mission_logs_status ON mission_logs(status);")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mission_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_log_id INTEGER NOT NULL,
            photo_path TEXT NOT NULL,
            note TEXT,
            executed_at TEXT,
            FOREIGN KEY(mission_log_id) REFERENCES mission_logs(id) ON DELETE CASCADE
        );
    """)
    # 기존 DB 마이그레이션: 인증 방식 관련 컬럼 추가
    mission_log_migration_cols = {
        "verification_type": "TEXT",        # 'photo' / 'transaction'
        "verification_keywords": "TEXT",    # 배달앱 이름 등, JSON 배열 문자열
    }
    for col, col_type in mission_log_migration_cols.items():
        if not _column_exists(conn, "mission_logs", col):
            cur.execute(f"ALTER TABLE mission_logs ADD COLUMN {col} {col_type};")
            print(f"[db] mission_logs.{col} 컬럼 추가 완료 (마이그레이션)")

    mission_exec_migration_cols = {
        "verified": "INTEGER",              # 0/1, NULL=검증 전
        "verification_reason": "TEXT",
        "confidence": "TEXT",               # high/medium/low
    }
    for col, col_type in mission_exec_migration_cols.items():
        if not _column_exists(conn, "mission_executions", col):
            cur.execute(f"ALTER TABLE mission_executions ADD COLUMN {col} {col_type};")
            print(f"[db] mission_executions.{col} 컬럼 추가 완료 (마이그레이션)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_mission_exec_mission ON mission_executions(mission_log_id);")

    # =========================================================
    # 6) transactions 테이블 (Android Room DB → 백엔드 동기화)
    # =========================================================
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tx_datetime TEXT NOT NULL,   -- ISO datetime, parser.py의 'datetime' 필드
            amount INTEGER NOT NULL,
            merchant TEXT NOT NULL,
            category TEXT,
            source TEXT,                 -- kakaopay/shinhan/kb/samsung/...
            payment_method TEXT,
            raw_text TEXT,
            synced_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_tx_user ON transactions(user_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_tx_datetime ON transactions(tx_datetime);")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_tx_merchant ON transactions(merchant);")

    # 중복 동기화 방지용 (같은 유저의 같은 거래가 여러 번 sync 안 되도록)
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_tx_dedup
        ON transactions(user_id, tx_datetime, amount, merchant);
    """)
    
    conn.commit()
    conn.close()

def now_iso():
    return datetime.now().isoformat(timespec="seconds")