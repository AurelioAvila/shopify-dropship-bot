"""
Pubblica un Reel su Instagram via Instagram API with Instagram Login
(token con prefisso IGAA, generati dal flusso "Instagram Business Login" in
Meta for Developers - non il vecchio flusso via Pagina Facebook).

Richiede un video_url PUBBLICO (l'API non accetta upload diretto di file
locali) - per questo generate_promo_videos + questo job caricano prima il
video su Shopify CDN (vedi ShopifyClient.upload_video_get_public_url).

Credenziali lette da: INSTAGRAM_{BRAND}_ACCESS_TOKEN, INSTAGRAM_{BRAND}_IG_USER_ID

Flusso ufficiale (Content Publishing API, host graph.instagram.com):
1. POST /{ig-user-id}/media  (video_url, caption, media_type=REELS) -> creation_id
2. polling di /{creation_id}?fields=status_code finche' non e' FINISHED
3. POST /{ig-user-id}/media_publish (creation_id) -> id del post pubblicato
Il token va passato come Bearer nell'header Authorization, non come parametro.

is_ai_generated=true (2026-08-05): l'AI Act europeo (Articolo 50) e' diventato
legalmente vincolante il 2026-08-02 - multe fino a 15 milioni di euro o il 3%
del fatturato globale per chi non etichetta contenuto generato/manipolato da
IA. Ogni video di questa pipeline usa voce sintetica (TTS) e script generati,
quindi rientra nell'obbligo. Questo e' il parametro NATIVO documentato da
Meta (developers.facebook.com/docs/instagram-platform/content-publishing/)
per farlo dichiarare all'account stesso, non solo un hashtag testuale che
l'utente puo' ignorare - Instagram applica poi da solo l'etichetta "AI info"
visibile sul post.
"""
import os
import time

import requests

API_BASE = "https://graph.instagram.com/v21.0"

# audio_name per brand (2026-08-06): l'algoritmo tratta l'audio come un tag
# di metadati con una propria pagina che raccoglie tutti i reel che lo
# usano - un nome brandizzato coerente la trasforma in un hub del brand e
# aggiunge una keyword di nicchia ricercabile. La musica di libreria via
# API non esiste (va incorporata nel file video prima dell'upload).
_AUDIO_NAME_BY_BRAND = {
    "GROOMLYCO": "Groomlyco Pet Care Finds",
    "MAGDOCK": "Magdock Tech Finds",
    "BEFFANTE": "Beffante Desk Setup Finds",
}


def upload_reel(brand: str, video_url: str, caption: str) -> str:
    access_token = os.environ[f"INSTAGRAM_{brand}_ACCESS_TOKEN"]
    ig_user_id = os.environ[f"INSTAGRAM_{brand}_IG_USER_ID"]
    headers = {"Authorization": f"Bearer {access_token}"}

    data = {"media_type": "REELS", "video_url": video_url, "caption": caption, "is_ai_generated": "true"}
    audio_name = _AUDIO_NAME_BY_BRAND.get(brand.upper())
    if audio_name:
        data["audio_name"] = audio_name

    create_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media",
        headers=headers,
        data=data,
    )
    if not create_resp.ok:
        print(f"[ERRORE] [{brand}] creazione media fallita: {create_resp.text}")
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    status = _poll_container_status(creation_id, headers)
    if status != "FINISHED":
        raise RuntimeError(f"[{brand}] Instagram non ha elaborato il video (stato: {status})")

    publish_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media_publish",
        headers=headers,
        data={"creation_id": creation_id},
    )
    publish_resp.raise_for_status()
    post_id = publish_resp.json()["id"]
    print(f"[OK] [{brand}] Reel pubblicato su Instagram: {post_id}")
    return post_id


def delete_media(brand: str, media_id: str) -> None:
    access_token = os.environ[f"INSTAGRAM_{brand}_ACCESS_TOKEN"]
    resp = requests.delete(
        f"{API_BASE}/{media_id}", headers={"Authorization": f"Bearer {access_token}"}
    )
    resp.raise_for_status()
    print(f"[OK] [{brand}] Rimosso post {media_id}")


def _poll_container_status(creation_id: str, headers: dict, timeout: int = 300) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{API_BASE}/{creation_id}", headers=headers, params={"fields": "status_code"})
        resp.raise_for_status()
        status = resp.json()["status_code"]
        if status in ("FINISHED", "ERROR"):
            return status
        time.sleep(5)
    return "TIMEOUT"
