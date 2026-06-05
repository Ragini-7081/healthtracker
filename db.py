import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "healthtrack.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
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
    # Add reminder_time column if it doesn't exist (for existing databases)
    try:
        cur.execute("ALTER TABLE habits ADD COLUMN reminder_time TEXT DEFAULT NULL")
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.close()
