import sqlite3
import os

class Database:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = os.getenv("DATABASE_URL", "parts.db")
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES parts(id) ON DELETE SET NULL
            )
        """)
        conn.commit()
        conn.close()

    def seed_data(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM parts")
        if cursor.fetchone()[0] == 0:
            cursor.executemany("""
                INSERT INTO parts (name, description, parent_id) VALUES (?, ?, ?)
            """, [
                ("Root Assembly", "Top-level assembly unit", None),
                ("Sub-assembly A", "Mechanical sub-assembly A", 1),
                ("Sub-assembly B", "Electrical sub-assembly B", 1),
                ("Part A1", "Bolt or nut for sub-assembly A", 2),
                ("Part B1", "Wire harness for sub-assembly B", 3)
            ])
            conn.commit()
        conn.close()
