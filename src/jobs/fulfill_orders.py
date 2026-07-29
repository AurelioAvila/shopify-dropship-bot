"""
Job 3: guarda gli ordini Shopify non evasi, e per ciascuno crea l'ordine
corrispondente su CJdropshipping (che spedisce al cliente finale).
Da schedulare (es. ogni 30-60 minuti).

Uso:
    python -m src.jobs.fulfill_orders
"""
from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.store import get_conn

COUNTRY_NAME_TO_CODE = {
    "Italy": "IT", "Italia": "IT",
    "United States": "US", "United Kingdom": "GB",
    "Germany": "DE", "France": "FR", "Spain": "ES",
}


def fulfill_new_orders() -> None:
    shopify = ShopifyClient()
    cj = CJClient()
    conn = get_conn()

    already_handled = {r[0] for r in conn.execute("SELECT shopify_order_id FROM order_map")}
    orders = shopify.list_unfulfilled_orders()
    new_orders = [o for o in orders if o["id"] not in already_handled]
    print(f"{len(new_orders)} nuovi ordini da evadere su {len(orders)} non evasi totali")

    for order in new_orders:
        shipping = order.get("shipping_address") or {}
        country_code = shipping.get("country_code") or COUNTRY_NAME_TO_CODE.get(shipping.get("country", ""), "IT")

        products = []
        skip_order = False
        for line_item in order["line_items"]:
            variant_id = line_item["variant_id"]
            row = conn.execute(
                "SELECT cj_vid FROM product_map WHERE shopify_variant_id = ?", (variant_id,)
            ).fetchone()
            if not row:
                print(f"  ! ordine {order['id']}: variante {variant_id} non mappata a CJ, salto (gestiscila a mano)")
                skip_order = True
                break
            products.append({"vid": row[0], "quantity": line_item["quantity"]})

        if skip_order or not products:
            continue

        try:
            cj_order = cj.create_order(
                order_number=f"shopify-{order['id']}",
                shipping_country_code=country_code,
                shipping_customer_name=f"{shipping.get('first_name', '')} {shipping.get('last_name', '')}".strip(),
                shipping_address={
                    "address1": shipping.get("address1", ""),
                    "address2": shipping.get("address2", ""),
                    "city": shipping.get("city", ""),
                    "province": shipping.get("province", ""),
                    "zip": shipping.get("zip", ""),
                    "phone": shipping.get("phone", ""),
                },
                products=products,
            )
            conn.execute(
                "INSERT INTO order_map (shopify_order_id, cj_order_id, cj_order_number, status) VALUES (?, ?, ?, ?)",
                (order["id"], cj_order.get("orderId"), cj_order.get("orderNumber"), "ordered"),
            )
            conn.commit()
            print(f"  + ordine Shopify {order['id']} -> ordine CJ {cj_order.get('orderId')}")
        except Exception as exc:
            print(f"  ! errore creando ordine CJ per Shopify order {order['id']}: {exc}")

    conn.close()


if __name__ == "__main__":
    fulfill_new_orders()
