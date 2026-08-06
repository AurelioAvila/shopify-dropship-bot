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
from src.copywriting import generate_description_html, generate_seo_description
from src.store import get_conn

# Fix 2026-08-03: create_product() accettava gia' un parametro vendor, ma
# questo job non lo passava mai - ogni prodotto veniva creato col default
# "Dropship", senza alcuna distinzione di brand. Scoperto durante un audit
# sul negozio pubblico: tutti i 116 prodotti esistenti avevano vendor
# "Dropship", quindi non poteva esistere una collezione per brand (ne' per
# Groomlyco ne' per Magdock) e il link "shop below" di entrambi gli account
# Instagram portava alla stessa homepage con prodotti pet e tech mischiati.
# Quel batch e' stato riclassificato una tantum a mano; questa e' la
# correzione strutturale perche' non debba succedere di nuovo sui prossimi
# import. Stesse keyword gia' verificate sull'intero catalogo esistente
# (116/116 classificati, 0 ambigui) - vedi memoria
# "feedback_store_branding_and_collections_fix".
PET_KEYWORDS = ("dog", "cat", "pet")
TECH_KEYWORDS = (
    "magsafe", "phone", "wireless car", "webcam", "camera", "usb", "bluetooth",
    "power bank", "laptop", "projector", "speaker", "smart watch",
    "cable organizer", "dash cam", "car seat", "car mount", "trunk",
)


def classify_vendor(keyword: str, title: str) -> str:
    """Groomlyco per prodotti pet, Magdock per prodotti tech - stessa logica
    (e stesse keyword) usate per la riclassificazione una tantum del
    catalogo esistente. 'Dropship' resta il fallback esplicito per un
    prodotto che non rientra in nessuna delle due nicchie, cosi' resta
    visibile/riconoscibile invece di finire silenziosamente in un brand
    sbagliato."""
    text = f"{keyword} {title}".lower()
    if any(k in text for k in PET_KEYWORDS):
        return "Groomlyco"
    if any(k in text for k in TECH_KEYWORDS):
        return "Magdock"
    return "Dropship"


def compute_sell_price(cost: float) -> float:
    markup = cost * (1 + config.MARKUP_PERCENT / 100)
    floor = cost + config.MIN_MARGIN_EUR
    raw = max(markup, floor)
    # Prezzo psicologico (2026-08-05): i prezzi grezzi della formula
    # (16.83, 7.53, 10.47...) sembrano calcolati da un algoritmo e non da un
    # negozio - arrotondiamo SEMPRE VERSO L'ALTO al .99 piu' vicino, cosi'
    # il margine non scende mai e il prezzo esposto e' quello standard
    # dell'e-commerce. Usato sia all'import sia dal sync ogni 6h
    # (sync_stock_price importa questa stessa funzione), quindi il prezzo
    # non viene mai riportato al valore grezzo.
    import math
    candidate = math.floor(raw) + 0.99
    if candidate < raw:
        candidate += 1.0
    return round(candidate, 2)


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
        vendor = classify_vendor(keyword, title)

        # Restyle 2026-08-05: descrizione benefit-driven generata da
        # src.copywriting invece del body grezzo CJ (keyword-stuffed,
        # spesso scritto male in inglese) - vedi commento li' per le regole
        # (niente specifiche inventate, niente "luxury").
        product = shopify.create_product(
            title=title,
            description_html=generate_description_html(title, vendor),
            price=sell_price,
            image_urls=images,
            product_type=keyword,
            vendor=vendor,
        )
        shopify_variant = product["variants"][0]

        seo_title = f"{title[:57 - len(vendor)]} | {vendor}"
        shopify._graphql(
            """
            mutation productUpdate($input: ProductInput!) {
              productUpdate(input: $input) { product { id } userErrors { field message } }
            }
            """,
            {"input": {
                "id": f"gid://shopify/Product/{product['id']}",
                "seo": {"title": seo_title, "description": generate_seo_description(title, vendor)},
            }},
        )

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
        print(f"  + importato [{vendor}]: {title} | costo {cost:.2f} -> vendita {sell_price:.2f}")

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True, help="Nicchia/parola chiave da cercare su CJ")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    import_keyword(args.keyword, args.limit)
