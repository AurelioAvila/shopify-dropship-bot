import os
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

    def delete_product(self, product_id: int) -> None:
        self._ensure_token()
        resp = self.session.delete(self._url(f"products/{product_id}.json"))
        resp.raise_for_status()

    def _graphql(self, query: str, variables: dict) -> dict:
        self._ensure_token()
        resp = self.session.post(self._url("graphql.json"), json={"query": query, "variables": variables})
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Errore GraphQL Shopify: {data['errors']}")
        return data["data"]

    def upload_video_get_public_url(self, file_path: str, alt: str = "") -> str:
        """Carica un file video su Shopify (CDN) e ne restituisce l'URL pubblico
        riproducibile, necessario per pubblicare Reels via Instagram Graph API
        (che richiede un video_url pubblico, non un upload diretto di file)."""
        filename = os.path.basename(file_path)
        file_size = str(os.path.getsize(file_path))

        staged = self._graphql(
            """
            mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
              stagedUploadsCreate(input: $input) {
                stagedTargets { url resourceUrl parameters { name value } }
                userErrors { field message }
              }
            }
            """,
            {"input": [{
                "filename": filename, "mimeType": "video/mp4",
                "resource": "VIDEO", "httpMethod": "POST", "fileSize": file_size,
            }]},
        )["stagedUploadsCreate"]
        if staged["userErrors"]:
            raise RuntimeError(f"stagedUploadsCreate error: {staged['userErrors']}")
        target = staged["stagedTargets"][0]

        form_data = {p["name"]: p["value"] for p in target["parameters"]}
        with open(file_path, "rb") as f:
            upload_resp = requests.post(target["url"], data=form_data, files={"file": (filename, f)})
        upload_resp.raise_for_status()

        created = self._graphql(
            """
            mutation fileCreate($files: [FileCreateInput!]!) {
              fileCreate(files: $files) {
                files { id fileStatus ... on Video { sources { url } } }
                userErrors { field message }
              }
            }
            """,
            {"files": [{"alt": alt, "contentType": "VIDEO", "originalSource": target["resourceUrl"]}]},
        )["fileCreate"]
        if created["userErrors"]:
            raise RuntimeError(f"fileCreate error: {created['userErrors']}")
        file_id = created["files"][0]["id"]

        return self._poll_file_ready(file_id)

    def _poll_file_ready(self, file_id: str, timeout: int = 120) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self._graphql(
                """
                query($id: ID!) {
                  node(id: $id) {
                    ... on Video { fileStatus sources { url } }
                  }
                }
                """,
                {"id": file_id},
            )
            node = data["node"]
            if node["fileStatus"] == "READY" and node["sources"]:
                return node["sources"][0]["url"]
            if node["fileStatus"] == "FAILED":
                raise RuntimeError("Elaborazione video fallita su Shopify")
            time.sleep(3)
        raise TimeoutError("Timeout in attesa che Shopify elabori il video")

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
