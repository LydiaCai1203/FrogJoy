import sqlite3
import os
from contextlib import contextmanager

DATABASE_PATH = "data/app.db"

def get_db_connection():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                title TEXT NOT NULL,
                creator TEXT,
                cover_url TEXT,
                file_path TEXT NOT NULL,
                is_public INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_opened_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_user_id ON books(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_books_is_public ON books(is_public)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS highlights (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                book_id TEXT NOT NULL,
                chapter_href TEXT NOT NULL,
                paragraph_index INTEGER NOT NULL DEFAULT 0,
                end_paragraph_index INTEGER NOT NULL DEFAULT 0,
                start_offset INTEGER NOT NULL DEFAULT 0,
                end_offset INTEGER NOT NULL DEFAULT 0,
                selected_text TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT 'yellow',
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_highlights_book_chapter ON highlights(book_id, chapter_href)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_highlights_user_book ON highlights(user_id, book_id)
        """)

        print("[Database] Initialized successfully")

if __name__ == "__main__":
    init_db()
