"""
Job 4: controlla lo stato degli ordini gia' inoltrati a CJ, e appena hanno un
tracking number segna l'ordine Shopify come evaso (spedito) col tracking.
Da schedulare (es. ogni 2-3 ore).

Uso:
    python -m src.jobs.update_tracking
"""
from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.store import get_conn


def update_all() -> None:
    cj = CJClient()
    shopify = ShopifyClient()
    conn = get_conn()

    pending = conn.execute(
        "SELECT shopify_order_id, cj_order_id FROM order_map WHERE status = 'ordered'"
    ).fetchall()
    print(f"Controllo tracking per {len(pending)} ordini in attesa di spedizione...")

    for shopify_order_id, cj_order_id in pending:
        detail = cj.get_order_detail(cj_order_id)
        tracking_number = detail.get("trackNumber")
        if not tracking_number:
            continue

        fulfillment_order_id = shopify.get_open_fulfillment_order_id(shopify_order_id)
        if not fulfillment_order_id:
            print(f"  ! ordine {shopify_order_id}: nessuna fulfillment order aperta trovata, salto")
            continue

        shopify.create_fulfillment(
            order_id=shopify_order_id,
            fulfillment_order_id=fulfillment_order_id,
            tracking_number=tracking_number,
            tracking_company=detail.get("trackingProvider", "CJPacket"),
        )
        print(f"  + ordine {shopify_order_id}: segnato come spedito, tracking {tracking_number}")

        conn.execute(
            "UPDATE order_map SET status = 'shipped', tracking_number = ?, tracking_company = ? "
            "WHERE shopify_order_id = ?",
            (tracking_number, detail.get("trackingProvider", ""), shopify_order_id),
        )
        conn.commit()

    conn.close()


if __name__ == "__main__":
    update_all()
