"""Pubblica un tweet di solo testo su X (Twitter) - free tier.

Perche' solo testo: il piano gratuito dell'API X v2 permette di postare
tweet (500/mese, 100/giorno per app) ma l'upload di media (immagini/video)
richiede il piano Basic a pagamento ($100/mese). Quindi qui pubblichiamo
solo caption + CTA/link allo store, niente video allegato.

Credenziali lette da (stesso pattern di instagram_upload.py):
    X_{BRAND}_API_KEY, X_{BRAND}_API_SECRET,
    X_{BRAND}_ACCESS_TOKEN, X_{BRAND}_ACCESS_TOKEN_SECRET

Se non impostate per un brand, post_tweet() salta silenziosamente invece
di sollevare un errore bloccante (comportamento opzionale, come per lo
step X del bot CertSprint gemello).
"""
import base64
import hashlib
import hmac
import os
import time
import uuid
from urllib.parse import quote

import requests

API_URL = "https://api.twitter.com/2/tweets"


def _load_creds(brand: str) -> dict | None:
    keys = {
        "api_key": f"X_{brand}_API_KEY",
        "api_secret": f"X_{brand}_API_SECRET",
        "access_token": f"X_{brand}_ACCESS_TOKEN",
        "access_token_secret": f"X_{brand}_ACCESS_TOKEN_SECRET",
    }
    values = {name: os.environ.get(env_name) for name, env_name in keys.items()}
    if not all(values.values()):
        return None
    return values


def _oauth_header(url: str, creds: dict) -> str:
    oauth_params = {
        "oauth_consumer_key": creds["api_key"],
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    param_string = "&".join(
        f"{quote(k, safe='')}={quote(str(oauth_params[k]), safe='')}" for k in sorted(oauth_params)
    )
    base_string = "&".join(["POST", quote(url, safe=""), quote(param_string, safe="")])
    signing_key = f"{quote(creds['api_secret'], safe='')}&{quote(creds['access_token_secret'], safe='')}"
    signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    oauth_params["oauth_signature"] = base64.b64encode(signature).decode()
    return "OAuth " + ", ".join(
        f'{quote(k, safe="")}="{quote(str(v), safe="")}"' for k, v in sorted(oauth_params.items())
    )


def post_tweet(brand: str, text: str) -> str | None:
    creds = _load_creds(brand)
    if creds is None:
        print(f"[x_upload] [{brand}] X_{brand}_API_* non impostate, salto il post su X.")
        return None

    headers = {
        "Authorization": _oauth_header(API_URL, creds),
        "Content-Type": "application/json",
    }
    resp = requests.post(API_URL, json={"text": text[:280]}, headers=headers, timeout=30)
    if not resp.ok:
        print(f"[ERRORE] [{brand}] post X fallito: {resp.text}")
        return None
    tweet_id = resp.json().get("data", {}).get("id")
    print(f"[OK] [{brand}] Pubblicato su X: {tweet_id}")
    return tweet_id
