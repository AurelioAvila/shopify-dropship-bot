import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {name}. Copia .env.example in .env e compilala.")
    return value


SHOPIFY_STORE_DOMAIN = _require("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ADMIN_API_TOKEN = _require("SHOPIFY_ADMIN_API_TOKEN")
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2024-10")

CJ_EMAIL = _require("CJ_EMAIL")
CJ_API_KEY = _require("CJ_API_KEY")

MARKUP_PERCENT = float(os.environ.get("MARKUP_PERCENT", "45"))
MIN_MARGIN_EUR = float(os.environ.get("MIN_MARGIN_EUR", "5"))
