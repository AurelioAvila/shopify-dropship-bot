"""
Pubblica un video su TikTok usando un refresh token gia' generato per un
determinato brand (vedi get_tiktok_token.py). Adattato dal bot YouTube Shorts
per supportare piu' account (uno per brand/nicchia) tramite il prefisso env var.

Credenziali lette da: TIKTOK_{BRAND}_CLIENT_KEY, TIKTOK_{BRAND}_CLIENT_SECRET,
TIKTOK_{BRAND}_REFRESH_TOKEN (es. TIKTOK_PET_CLIENT_KEY, TIKTOK_TECH_CLIENT_KEY).

Flusso ufficiale Content Posting API v2:
1. refresh access token
2. query creator_info -> privacy_level disponibili per l'account
3. init publish (FILE_UPLOAD) -> upload_url + publish_id
4. upload del file video su upload_url
5. polling dello stato fino a PUBLISH_COMPLETE / FAILED

NB: finche' l'app non ha superato l'audit "Direct Post" di TikTok, la
privacy_level effettiva resta SELF_ONLY anche se richiediamo PUBLIC_TO_EVERYONE.
"""
import os
import time

import requests

API_BASE = "https://open.tiktokapis.com/v2"
TITLE_MAX_LEN = 2200


def _get_access_token(brand: str) -> str:
    resp = requests.post(
        f"{API_BASE}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ[f"TIKTOK_{brand}_CLIENT_KEY"],
            "client_secret": os.environ[f"TIKTOK_{brand}_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": os.environ[f"TIKTOK_{brand}_REFRESH_TOKEN"],
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"Refresh del token TikTok fallito per brand {brand}: {data}")
    return data["access_token"]


def _query_available_privacy_levels(access_token: str) -> list:
    resp = requests.post(
        f"{API_BASE}/post/publish/creator_info/query/",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if "data" not in data:
        raise RuntimeError(f"Query creator_info fallita: {data}")
    return data["data"]["privacy_level_options"]


def _safe_truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def upload_video(brand: str, video_path: str, caption: str, privacy_level: str = "SELF_ONLY") -> str:
    access_token = _get_access_token(brand)

    available = _query_available_privacy_levels(access_token)
    print(f"[INFO] [{brand}] privacy_level disponibili: {available}")
    if privacy_level not in available:
        print(f"[WARN] [{brand}] '{privacy_level}' non disponibile; TikTok assegnera' un livello valido.")

    video_size = os.path.getsize(video_path)

    init_resp = requests.post(
        f"{API_BASE}/post/publish/video/init/",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "post_info": {
                "title": _safe_truncate(caption, TITLE_MAX_LEN),
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_comment": False,
                "disable_stitch": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        },
    )
    if not init_resp.ok:
        print(f"[ERRORE] [{brand}] init publish fallito ({init_resp.status_code}): {init_resp.text}")
    init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    with open(video_path, "rb") as f:
        video_bytes = f.read()
    put_resp = requests.put(
        upload_url,
        headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{video_size - 1}/{video_size}"},
        data=video_bytes,
    )
    put_resp.raise_for_status()

    status = _poll_publish_status(access_token, publish_id)
    print(f"[OK] [{brand}] Pubblicato su TikTok: publish_id={publish_id}, stato={status}")
    return publish_id


def upload_video_to_inbox(brand: str, video_path: str) -> str:
    """Manda il video nella casella bozze ("Upload to TikTok") del profilo del
    brand, invece di pubblicarlo direttamente - funziona anche prima che
    l'audit "Direct Post" sia approvato, perche' non e' soggetto alle
    restrizioni sul privacy_level (non pubblica nulla da solo).

    Limite noto dell'endpoint /inbox/video/init/: non accetta un post_info,
    quindi non possiamo precompilare titolo/caption via API - il brand deve
    incollarla a mano nell'app quando apre la bozza per pubblicarla."""
    access_token = _get_access_token(brand)
    video_size = os.path.getsize(video_path)

    init_resp = requests.post(
        f"{API_BASE}/post/publish/inbox/video/init/",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": video_size,
                "chunk_size": video_size,
                "total_chunk_count": 1,
            },
        },
    )
    if not init_resp.ok:
        print(f"[ERRORE] [{brand}] init inbox fallito ({init_resp.status_code}): {init_resp.text}")
    init_resp.raise_for_status()
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    with open(video_path, "rb") as f:
        video_bytes = f.read()
    put_resp = requests.put(
        upload_url,
        headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{video_size - 1}/{video_size}"},
        data=video_bytes,
    )
    put_resp.raise_for_status()

    status = _poll_publish_status(access_token, publish_id)
    print(f"[OK] [{brand}] Inviato nelle bozze TikTok: publish_id={publish_id}, stato={status}")
    return publish_id


def _poll_publish_status(access_token: str, publish_id: str, timeout: int = 120) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.post(
            f"{API_BASE}/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"publish_id": publish_id},
        )
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        if status in ("PUBLISH_COMPLETE", "FAILED"):
            return status
        time.sleep(3)
    return "TIMEOUT"
