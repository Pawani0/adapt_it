import os
import sqlite3

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        correct_answer TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        opened_at TEXT,
        submitted_at TEXT,
        time_taken INTEGER,
        score INTEGER,
        answers TEXT,
        tab_switches INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sent_questions (
        id TEXT PRIMARY KEY,
        question_text TEXT,
        topic TEXT,
        first_sent_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidate_memory (
        email TEXT PRIMARY KEY,
        payload_json TEXT NOT NULL
    )
    """,
]


class DBConnection:
    def __init__(self, conn, is_postgres: bool):
        self._conn = conn
        self._is_postgres = is_postgres

    def _normalize_query(self, query: str) -> str:
        if self._is_postgres:
            return query.replace("?", "%s")
        return query

    def execute(self, query: str, params=()):
        sql = self._normalize_query(query)
        if self._is_postgres:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


def using_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL", "").strip())


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def _sqlite_db_path() -> str:
    return os.environ.get("QUIZ_DB_FILE", "quiz.db")


def connect():
    if using_postgres():
        if psycopg is None:
            raise RuntimeError("psycopg is required when DATABASE_URL is configured.")
        conn = psycopg.connect(_database_url(), row_factory=dict_row)
        return DBConnection(conn, True)

    db_path = _sqlite_db_path()
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return DBConnection(conn, False)


def initialize_schema():
    with connect() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
