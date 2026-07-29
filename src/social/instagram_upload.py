"""
Pubblica un Reel su Instagram via Meta Graph API, per un brand specifico.

Richiede un video_url PUBBLICO (l'API non accetta upload diretto di file
locali) - per questo generate_promo_videos + questo job caricano prima il
video su Shopify CDN (vedi ShopifyClient.upload_video_get_public_url).

Credenziali lette da: INSTAGRAM_{BRAND}_ACCESS_TOKEN, INSTAGRAM_{BRAND}_IG_USER_ID
(access token di lunga durata + ID dell'account Instagram Business/Creator,
generati una tantum da https://developers.facebook.com/ - Meta for Developers).

Flusso ufficiale (Content Publishing API):
1. POST /{ig-user-id}/media  (video_url, caption, media_type=REELS) -> creation_id
2. polling di /{creation_id}?fields=status_code finche' non e' FINISHED
3. POST /{ig-user-id}/media_publish (creation_id) -> id del post pubblicato
"""
import os
import time

import requests

API_BASE = "https://graph.facebook.com/v21.0"


def upload_reel(brand: str, video_url: str, caption: str) -> str:
    access_token = os.environ[f"INSTAGRAM_{brand}_ACCESS_TOKEN"]
    ig_user_id = os.environ[f"INSTAGRAM_{brand}_IG_USER_ID"]

    create_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": access_token,
        },
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    status = _poll_container_status(creation_id, access_token)
    if status != "FINISHED":
        raise RuntimeError(f"[{brand}] Instagram non ha elaborato il video (stato: {status})")

    publish_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
    )
    publish_resp.raise_for_status()
    post_id = publish_resp.json()["id"]
    print(f"[OK] [{brand}] Reel pubblicato su Instagram: {post_id}")
    return post_id


def _poll_container_status(creation_id: str, access_token: str, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
        )
        resp.raise_for_status()
        status = resp.json()["status_code"]
        if status in ("FINISHED", "ERROR"):
            return status
        time.sleep(5)
    return "TIMEOUT"
