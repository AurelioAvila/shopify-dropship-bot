"""
Job 2: ricontrolla presso CJ lo stock e il prezzo dei prodotti gia' importati,
e aggiorna Shopify di conseguenza. Da schedulare (es. ogni 6 ore).

Uso:
    python -m src.jobs.sync_stock_price
"""
from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.jobs.import_products import compute_sell_price
from src.store import get_conn


def sync_all() -> None:
    cj = CJClient()
    shopify = ShopifyClient()
    conn = get_conn()
    location_id = shopify.get_primary_location_id()

    rows = conn.execute("SELECT * FROM product_map").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM product_map").description]

    print(f"Sincronizzo {len(rows)} varianti...")
    for row in rows:
        r = dict(zip(cols, row))
        stock = cj.get_stock(r["cj_vid"])
        available = int(stock.get("totalInventoryNum", 0))

        detail = cj.get_product_detail(r["cj_pid"])
        variant = next((v for v in detail.get("variants", []) if v.get("vid") == r["cj_vid"]), None)
        cost = float(variant["variantSellPrice"]) if variant else r["cost_price"]
        new_price = compute_sell_price(cost)

        shopify.update_variant_price_and_stock(
            variant_id=r["shopify_variant_id"],
            inventory_item_id=r["shopify_inventory_item_id"],
            location_id=location_id,
            price=new_price,
            available=available,
        )

        conn.execute(
            "UPDATE product_map SET cost_price = ?, sell_price = ? WHERE shopify_variant_id = ?",
            (cost, new_price, r["shopify_variant_id"]),
        )
        conn.commit()
        print(f"  - variant {r['shopify_variant_id']}: stock={available} prezzo={new_price:.2f}")

    conn.close()


if __name__ == "__main__":
    sync_all()
