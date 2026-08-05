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

# Su YouTube non esiste il "link in bio" di IG/TikTok: la descrizione E' il
# funnel. Ogni video chiude col link alla collezione del proprio brand -
# handle verificati LIVE su /collections.json il 2026-08-06, non supposti.
STORE_LINKS = {
    "GROOMLYCO": "\U0001F6D2 Shop it here → https://91zey8-ha.myshopify.com/collections/groomlyco",
    "MAGDOCK": "\U0001F6D2 Shop it here → https://91zey8-ha.myshopify.com/collections/magdock",
    "BEFFANTE": "\U0001F6D2 Shop it here → https://91zey8-ha.myshopify.com/collections/beffante",
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
    store_link = STORE_LINKS.get(brand)
    if store_link and "myshopify.com" not in description:
        # In TESTA e non in coda: YouTube mostra solo le prime righe della
        # descrizione senza "...altro", e il link e' l'unica azione che
        # vogliamo dallo spettatore.
        description = store_link + "\n\n" + description.lstrip()
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
    try:
        from src.thumbnail import build_short_thumbnail, upload_thumbnail

        if not thumbnail_path:
            # Short senza copertina esplicita (2026-08-06): finora la
            # sceglieva YouTube da un fotogramma a caso, con addosso il
            # sottotitolo troncato a meta' parola. Ora si costruisce dal
            # primo fotogramma, che porta gia' la hook card del promo.
            thumbnail_path = os.path.join(
                os.path.dirname(os.path.abspath(video_path)), "thumbnail.jpg")
            build_short_thumbnail(video_path, thumbnail_path, title=None, brand=brand)
        upload_thumbnail(youtube, response["id"], thumbnail_path)
    except Exception as exc:
        print(f"[thumbnail] non impostata ({exc}) - resta quella automatica", flush=True)

    return response["id"]
