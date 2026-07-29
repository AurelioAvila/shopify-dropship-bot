import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mapping.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_map (
            shopify_variant_id INTEGER PRIMARY KEY,
            shopify_product_id INTEGER NOT NULL,
            shopify_inventory_item_id INTEGER NOT NULL,
            cj_pid TEXT NOT NULL,
            cj_vid TEXT NOT NULL,
            cj_sku TEXT,
            cost_price REAL NOT NULL,
            sell_price REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_map (
            shopify_order_id INTEGER PRIMARY KEY,
            cj_order_id TEXT,
            cj_order_number TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            tracking_number TEXT,
            tracking_company TEXT
        )
    """)
    conn.commit()
    return conn
