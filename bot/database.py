import sqlite3, os
from contextlib import contextmanager

DB_PATH = os.getenv('DB_PATH', '/app/data/family_bot.db')

def init_db():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS user_calendars (
                telegram_id INTEGER PRIMARY KEY,
                name        TEXT NOT NULL,
                calendar_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                remind_at   TEXT NOT NULL,  -- ISO datetime
                message     TEXT NOT NULL,
                sent        INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS birthdays (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                added_by    INTEGER NOT NULL,
                name        TEXT NOT NULL,
                birth_date  TEXT NOT NULL   -- MM-DD
                );
        ''')

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()