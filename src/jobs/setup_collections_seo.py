"""
Job 9: crea collezioni per nicchia (migliora navigazione/conversione) e
imposta i meta tag SEO (titolo/descrizione) su tutti i prodotti, per
aiutare la scoperta organica via motori di ricerca.

Uso:
    python -m src.jobs.setup_collections_seo
"""
from src.clients.shopify_client import ShopifyClient

PET_KEYWORDS = ["Dog", "Pet", "Cat", "Grooming", "Nail", "Ramp", "Brace", "Leg"]
TECH_KEYWORDS = ["Phone", "Magsafe", "Car", "Charger", "USB", "Wireless", "Lanyard", "Cable"]


def _classify(title: str) -> str:
    if any(k in title for k in PET_KEYWORDS):
        return "pet"
    if any(k in title for k in TECH_KEYWORDS):
        return "tech"
    return "other"


def create_collections(shopify: ShopifyClient, pet_ids: list[int], tech_ids: list[int]) -> None:
    collections = [
        {
            "title": "Pet Grooming & Care",
            "body_html": "<p>Grooming tools, comfort accessories, and mobility support for dogs and cats.</p>",
            "ids": pet_ids,
            "seo_title": "Pet Grooming & Care Products | Nail Trimmers, Ramps, Comfort Gear",
            "seo_description": "Shop grooming tools, senior mobility support, and comfort accessories for dogs and cats. Fast shipping, tested quality.",
        },
        {
            "title": "Phone & Car Accessories",
            "body_html": "<p>MagSafe cases, car mounts, chargers, and everyday phone accessories.</p>",
            "ids": tech_ids,
            "seo_title": "Phone & Car Accessories | MagSafe Cases, Car Mounts, Chargers",
            "seo_description": "Shop MagSafe-compatible cases, magnetic car mounts, fast chargers, and phone accessories built to last.",
        },
    ]

    for c in collections:
        resp = shopify.session.post(
            shopify._url("custom_collections.json"),
            json={"custom_collection": {"title": c["title"], "body_html": c["body_html"], "published": True}},
        )
        resp.raise_for_status()
        collection_id = resp.json()["custom_collection"]["id"]
        print(f"  + collezione creata: {c['title']} (id {collection_id})")

        for pid in c["ids"]:
            r = shopify.session.post(
                shopify._url("collects.json"),
                json={"collect": {"collection_id": collection_id, "product_id": pid}},
            )
            r.raise_for_status()

        seo_resp = shopify._graphql(
            """
            mutation collectionUpdate($input: CollectionInput!) {
              collectionUpdate(input: $input) {
                collection { id }
                userErrors { field message }
              }
            }
            """,
            {
                "input": {
                    "id": f"gid://shopify/Collection/{collection_id}",
                    "seo": {"title": c["seo_title"], "description": c["seo_description"]},
                }
            },
        )
        errors = seo_resp["collectionUpdate"]["userErrors"]
        if errors:
            print(f"    ! SEO collezione fallito: {errors}")
        else:
            print(f"    + SEO impostato per {c['title']}")


def set_product_seo(shopify: ShopifyClient, products: list[dict]) -> None:
    for p in products:
        title = p["title"]
        short_title = title[:60].rsplit(" ", 1)[0] if len(title) > 60 else title
        seo_title = f"{short_title} | Fast Shipping"
        seo_description = (title[:145].rsplit(" ", 1)[0] if len(title) > 145 else title) + " - shop now."

        result = shopify._graphql(
            """
            mutation productUpdate($input: ProductInput!) {
              productUpdate(input: $input) {
                product { id }
                userErrors { field message }
              }
            }
            """,
            {
                "input": {
                    "id": f"gid://shopify/Product/{p['id']}",
                    "seo": {"title": seo_title, "description": seo_description},
                }
            },
        )["productUpdate"]
        if result["userErrors"]:
            print(f"  ! SEO fallito per {title[:40]}: {result['userErrors']}")
        else:
            print(f"  + SEO impostato: {title[:50]}")


def run() -> None:
    shopify = ShopifyClient()
    products = shopify.list_products(limit=250)

    pet_ids = [p["id"] for p in products if _classify(p["title"]) == "pet"]
    tech_ids = [p["id"] for p in products if _classify(p["title"]) == "tech"]
    print(f"Pet: {len(pet_ids)} | Tech: {len(tech_ids)} | Non classificati: {len(products) - len(pet_ids) - len(tech_ids)}")

    create_collections(shopify, pet_ids, tech_ids)
    set_product_seo(shopify, products)


if __name__ == "__main__":
    run()
