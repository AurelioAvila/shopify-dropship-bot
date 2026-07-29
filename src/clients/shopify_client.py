import time

import requests

from src import config


class ShopifyClient:
    def __init__(self):
        self.base_url = f"https://{config.SHOPIFY_STORE_DOMAIN}/admin/api/{config.SHOPIFY_API_VERSION}"
        self.session = requests.Session()
        self._token = None
        self._token_expiry = 0
        self._refresh_token()

    def _refresh_token(self) -> None:
        resp = requests.post(
            f"https://{config.SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token",
            json={
                "client_id": config.SHOPIFY_CLIENT_ID,
                "client_secret": config.SHOPIFY_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        # rinnova un po' prima della scadenza reale (di solito 24h) per sicurezza
        self._token_expiry = time.time() + data.get("expires_in", 3600) - 300
        self.session.headers.update({
            "X-Shopify-Access-Token": self._token,
            "Content-Type": "application/json",
        })

    def _ensure_token(self) -> None:
        if time.time() >= self._token_expiry:
            self._refresh_token()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def create_product(self, title: str, description_html: str, price: float, image_urls: list[str],
                        vendor: str = "Dropship", product_type: str = "") -> dict:
        self._ensure_token()
        payload = {
            "product": {
                "title": title,
                "body_html": description_html,
                "vendor": vendor,
                "product_type": product_type,
                "images": [{"src": url} for url in image_urls],
                "variants": [{"price": f"{price:.2f}", "inventory_management": "shopify"}],
            }
        }
        resp = self.session.post(self._url("products.json"), json=payload)
        resp.raise_for_status()
        return resp.json()["product"]

    def update_variant_price_and_stock(self, variant_id: int, inventory_item_id: int, location_id: int,
                                        price: float, available: int) -> None:
        self._ensure_token()
        resp = self.session.put(
            self._url(f"variants/{variant_id}.json"),
            json={"variant": {"id": variant_id, "price": f"{price:.2f}"}},
        )
        resp.raise_for_status()

        resp = self.session.post(
            self._url("inventory_levels/set.json"),
            json={
                "location_id": location_id,
                "inventory_item_id": inventory_item_id,
                "available": available,
            },
        )
        resp.raise_for_status()

    def list_products(self, limit: int = 250) -> list[dict]:
        self._ensure_token()
        resp = self.session.get(self._url("products.json"), params={"limit": limit})
        resp.raise_for_status()
        return resp.json()["products"]

    def list_unfulfilled_orders(self) -> list[dict]:
        self._ensure_token()
        resp = self.session.get(
            self._url("orders.json"),
            params={"status": "open", "fulfillment_status": "unfulfilled"},
        )
        resp.raise_for_status()
        return resp.json()["orders"]

    def create_fulfillment(self, order_id: int, fulfillment_order_id: int, tracking_number: str,
                            tracking_company: str, tracking_url: str = "") -> dict:
        self._ensure_token()
        payload = {
            "fulfillment": {
                "line_items_by_fulfillment_order": [{"fulfillment_order_id": fulfillment_order_id}],
                "tracking_info": {
                    "number": tracking_number,
                    "company": tracking_company,
                    "url": tracking_url,
                },
                "notify_customer": True,
            }
        }
        resp = self.session.post(self._url("fulfillments.json"), json=payload)
        resp.raise_for_status()
        return resp.json()["fulfillment"]

    def get_open_fulfillment_order_id(self, order_id: int) -> int | None:
        self._ensure_token()
        resp = self.session.get(self._url(f"orders/{order_id}/fulfillment_orders.json"))
        resp.raise_for_status()
        fulfillment_orders = resp.json()["fulfillment_orders"]
        open_ones = [fo for fo in fulfillment_orders if fo["status"] == "open"]
        return open_ones[0]["id"] if open_ones else None

    def get_primary_location_id(self) -> int:
        self._ensure_token()
        resp = self.session.get(self._url("locations.json"))
        resp.raise_for_status()
        locations = resp.json()["locations"]
        return locations[0]["id"]
