"""
Job 1: cerca prodotti su CJdropshipping per una parola chiave/nicchia,
li importa nello store Shopify con markup automatico, e salva la mappatura
Shopify <-> CJ in locale (necessaria per l'evasione ordini automatica).

Uso:
    python -m src.jobs.import_products --keyword "led lamp" --limit 5
"""
import argparse

from src import config
from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.store import get_conn


def compute_sell_price(cost: float) -> float:
    markup = cost * (1 + config.MARKUP_PERCENT / 100)
    floor = cost + config.MIN_MARGIN_EUR
    return round(max(markup, floor), 2)


def import_keyword(keyword: str, limit: int = 10) -> None:
    cj = CJClient()
    shopify = ShopifyClient()
    conn = get_conn()

    results = cj.search_products(keyword=keyword, size=limit)
    print(f"Trovati {len(results)} prodotti per '{keyword}'")

    for item in results:
        pid = item["id"]
        detail = cj.get_product_detail(pid)
        title = detail.get("productNameEn") or item.get("nameEn")
        images = detail.get("productImageSet") or ([detail["bigImage"]] if detail.get("bigImage") else [])
        variants = detail.get("variants", [])
        if not variants:
            print(f"  - skip {title}: nessuna variante trovata")
            continue

        variant = variants[0]
        cost = float(variant.get("variantSellPrice", item.get("sellPrice", 0)))
        if cost <= 0:
            print(f"  - skip {title}: prezzo fornitore non valido")
            continue

        sell_price = compute_sell_price(cost)

        product = shopify.create_product(
            title=title,
            description_html=detail.get("description", ""),
            price=sell_price,
            image_urls=images,
            product_type=keyword,
        )
        shopify_variant = product["variants"][0]

        conn.execute(
            """INSERT OR REPLACE INTO product_map
               (shopify_variant_id, shopify_product_id, shopify_inventory_item_id,
                cj_pid, cj_vid, cj_sku, cost_price, sell_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                shopify_variant["id"],
                product["id"],
                shopify_variant["inventory_item_id"],
                pid,
                variant.get("vid", ""),
                variant.get("variantSku", ""),
                cost,
                sell_price,
            ),
        )
        conn.commit()
        print(f"  + importato: {title} | costo {cost:.2f} -> vendita {sell_price:.2f}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True, help="Nicchia/parola chiave da cercare su CJ")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    import_keyword(args.keyword, args.limit)
