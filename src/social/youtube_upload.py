"""
Pubblica un video su YouTube per un brand specifico (Groomlyco o Magdock),
ognuno con le proprie credenziali - stesso principio multi-brand gia' usato
in tiktok_upload.py.

Credenziali lette da: YOUTUBE_{BRAND}_CLIENT_ID, YOUTUBE_{BRAND}_CLIENT_SECRET,
YOUTUBE_{BRAND}_REFRESH_TOKEN (es. YOUTUBE_GROOMLYCO_CLIENT_ID), generate con
get_youtube_token.py --brand groomlyco (nella root del repo).
"""
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CATEGORY_IDS = {
    "GROOMLYCO": "26",  # Howto & Style (pet care)
    "MAGDOCK": "26",    # Howto & Style (tech accessories)
    "BEFFANTE": "28",   # Science & Technology (proiettori/webcam/smart home)
}


def _get_authenticated_service(brand: str):
    creds = Credentials(
        token=None,
        refresh_token=os.environ[f"YOUTUBE_{brand}_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ[f"YOUTUBE_{brand}_CLIENT_ID"],
        client_secret=os.environ[f"YOUTUBE_{brand}_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(brand: str, video_path: str, title: str, description: str, tags: list = None,
                 thumbnail_path: str = None) -> str:
    youtube = _get_authenticated_service(brand)

    # Trasparenza AI (2026-08-05): EU AI Act art. 50, applicabile dal 2
    # agosto 2026 - i contenuti generati da AI vanno resi identificabili con
    # marcatura machine-readable. Questi promo sono interamente generati
    # (script assemblato + voce TTS su foto prodotto): il flag e' il campo
    # che l'API YouTube espone apposta, "#ai" e' la parte visibile.
    tags = list(tags or [])
    if not any(t.lower() == "ai" for t in tags):
        tags.append("ai")
    if "#ai" not in description.lower():
        description = description.rstrip() + "\n\n#ai"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags,
            "categoryId": CATEGORY_IDS.get(brand, "26"),
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload in corso: {int(status.progress() * 100)}%")

    print(f"[OK] [{brand}] Pubblicato su YouTube: video id={response['id']}")

    # Miniatura personalizzata (solo dove il chiamante la fornisce, in pratica
    # i buying guide long-form: sugli Shorts il feed parte in autoplay e la
    # miniatura conta pochissimo). upload_thumbnail non solleva mai, quindi un
    # canale senza telefono verificato non fa fallire una pubblicazione gia'
    # andata a buon fine.
    if thumbnail_path:
        from src.thumbnail import upload_thumbnail
        upload_thumbnail(youtube, response["id"], thumbnail_path)

    return response["id"]
