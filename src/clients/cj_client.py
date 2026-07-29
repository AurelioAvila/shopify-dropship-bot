"""
Client per le API di CJdropshipping (API v2.0).
Doc ufficiale: https://developers.cjdropshipping.cn/en/api/api2/

Nota: gli endpoint qui sotto sono quelli documentati al momento della scrittura.
CJ aggiorna periodicamente l'API: se una chiamata fallisce con 404/410, controlla
la doc ufficiale per l'eventuale nuovo path prima di pensare a un bug nel codice.
"""
import time

import requests

from src import config

BASE_URL = "https://developers.cjdropshipping.com/api2.0/v1"


class CJClient:
    def __init__(self):
        self._token = None
        self._token_expiry = 0
        self.session = requests.Session()

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry:
            return self._token

        resp = self.session.post(
            f"{BASE_URL}/authentication/getAccessToken",
            json={"apiKey": config.CJ_API_KEY},
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        self._token = data["accessToken"]
        # rinnova un po' prima della scadenza reale per sicurezza
        self._token_expiry = time.time() + 23 * 3600
        return self._token

    def _headers(self) -> dict:
        return {"CJ-Access-Token": self._get_token(), "Content-Type": "application/json"}

    def _request(self, method: str, url: str, max_retries: int = 5, **kwargs) -> requests.Response:
        """Chiama l'API CJ ritentando in automatico sui 429 (rate limit stretto lato CJ)."""
        for attempt in range(max_retries):
            resp = self.session.request(method, url, headers=self._headers(), **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            wait = float(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"    (rate limit CJ, riprovo tra {wait:.0f}s...)")
            time.sleep(wait)
        resp.raise_for_status()
        return resp

    def search_products(self, keyword: str = "", category_id: str = "", page: int = 1,
                         size: int = 20, min_price: float | None = None,
                         max_price: float | None = None) -> list[dict]:
        params = {"page": page, "size": size}
        if keyword:
            params["keyWord"] = keyword
        if category_id:
            params["categoryId"] = category_id
        if min_price is not None:
            params["startSellPrice"] = min_price
        if max_price is not None:
            params["endSellPrice"] = max_price

        resp = self._request("GET", f"{BASE_URL}/product/listV2", params=params)
        content = resp.json()["data"]["content"]
        products = []
        for group in content:
            products.extend(group.get("productList", []))
        return products

    def get_product_detail(self, pid: str) -> dict:
        resp = self._request("GET", f"{BASE_URL}/product/query", params={"pid": pid})
        return resp.json()["data"]

    def get_total_stock(self, vid: str) -> int:
        """Somma lo stock disponibile su tutti i magazzini per una variante."""
        resp = self._request("GET", f"{BASE_URL}/product/stock/queryByVid", params={"vid": vid})
        warehouses = resp.json()["data"]
        return sum(w.get("totalInventoryNum", 0) for w in warehouses)

    def create_order(self, order_number: str, shipping_country_code: str, shipping_customer_name: str,
                      shipping_address: dict, products: list[dict], logistic_name: str = "CJPacket") -> dict:
        payload = {
            "orderNumber": order_number,
            "shippingCountryCode": shipping_country_code,
            "shippingCustomerName": shipping_customer_name,
            "shippingAddress": shipping_address,
            "logisticName": logistic_name,
            "products": products,
        }
        resp = self._request("POST", f"{BASE_URL}/shopping/order/createOrderV2", json=payload)
        return resp.json()["data"]

    def get_order_detail(self, order_id: str) -> dict:
        resp = self._request("GET", f"{BASE_URL}/shopping/order/getOrderDetail", params={"orderId": order_id})
        return resp.json()["data"]
