import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "dairy.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript((BASE_DIR / "schema.sql").read_text(encoding="utf-8"))

    # Add starter products only if the table is empty
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO products (name, unit, rate_per_unit) VALUES (?, ?, ?)",
            [
                ("Milk", "litre", 56.0),
                ("Curd", "kg", 80.0),
                ("Paneer", "kg", 360.0),
                ("Ghee", "kg", 600.0),
            ],
        )
    conn.commit()
    conn.close()