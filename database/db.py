"""Database connection and schema management."""
import sqlite3
import os
from contextlib import contextmanager

# Default database path - store in config directory
DB_PATH = os.environ.get('MAO_DB_PATH', os.path.join(os.path.dirname(__file__), '..', 'config', 'mao_game.db'))

_connection = None


def get_connection():
    """Get or create database connection."""
    global _connection
    if _connection is None:
        # Ensure config directory exists
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        init_db(_connection)
    return _connection


@contextmanager
def get_db():
    """Context manager for database access."""
    conn = get_connection()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise


def init_db(conn=None):
    """Initialize database tables."""
    if conn is None:
        conn = get_connection()

    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_code TEXT,
            won BOOLEAN,
            cards_played INTEGER DEFAULT 0,
            penalties_given INTEGER DEFAULT 0,
            penalties_received INTEGER DEFAULT 0,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_game_history_user ON game_history(user_id);
    ''')
    conn.commit()


def close_db():
    """Close database connection."""
    global _connection
    if _connection:
        _connection.close()
        _connection = None