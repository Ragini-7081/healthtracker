import os
import sqlite3

# Check if running on production (PostgreSQL) or local (SQLite)
DATABASE_URL = os.environ.get("DATABASE_URL")

USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    from psycopg2.extensions import parse_dsn

def get_connection():
    if USE_POSTGRES:
        # Render gives postgres:// but psycopg2 needs postgresql://
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url, sslmode="require")
        return conn
    else:
        DB_PATH = os.path.join(os.path.dirname(__file__), "healthtrack.db")
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'fitness',
                frequency TEXT DEFAULT 'daily',
                goal TEXT,
                description TEXT,
                reminder_time TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id SERIAL PRIMARY KEY,
                habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                logged_date DATE NOT NULL,
                UNIQUE(habit_id, logged_date),
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            )
        """)
        conn.commit()
        # Add reminder_time column if it doesn't exist (migration for older DBs)
        try:
            cur.execute("ALTER TABLE habits ADD COLUMN reminder_time TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            conn.rollback()
    else:
        # SQLite (local development)
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'fitness',
                frequency TEXT DEFAULT 'daily',
                goal TEXT,
                description TEXT,
                reminder_time TEXT DEFAULT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                logged_date DATE NOT NULL,
                UNIQUE(habit_id, logged_date),
                FOREIGN KEY (habit_id) REFERENCES habits(id)
            );
        """)
        try:
            cur.execute("ALTER TABLE habits ADD COLUMN reminder_time TEXT DEFAULT NULL")
            conn.commit()
        except Exception:
            pass

    conn.close()


def query(sql, params=(), fetchone=False, fetchall=False, commit=False):
    """
    Universal query helper that works for both SQLite and PostgreSQL.
    PostgreSQL uses %s placeholders, SQLite uses ?.
    """
    conn = get_connection()

    if USE_POSTGRES:
        # Replace ? with %s for PostgreSQL
        sql = sql.replace("?", "%s")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()

    cur.execute(sql, params)

    result = None
    if fetchone:
        row = cur.fetchone()
        result = dict(row) if row else None
    elif fetchall:
        rows = cur.fetchall()
        result = [dict(r) for r in rows]

    if commit:
        conn.commit()

    conn.close()
    return result
