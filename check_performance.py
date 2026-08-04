"""Controllo performance YouTube per i 3 brand Shopify (Groomlyco, Magdock,
Beffante). Sola lettura: non pubblica e non modifica nulla.

Perche' esiste (2026-08-04): questi tre canali erano gli unici senza alcun
monitoraggio - i loro token avevano solo lo scope `youtube.upload`, quindi
non era tecnicamente possibile leggerne le statistiche. Rigenerati oggi con
`youtube.readonly` + `yt-analytics.readonly`, questo script chiude il buco.

Riporta la RETENTION, non solo le views: e' la metrica che decide se un
video viene spinto oltre il pool di test iniziale (~50-500 spettatori).
Soglie di riferimento 2026: ~65% sotto i 30s, ~50% tra 30 e 60s.

Uso:
    python check_performance.py                  # tutti i brand
    python check_performance.py --brand magdock  # uno solo
"""
import argparse
import os
import re
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import src.config  # noqa: F401  - carica .env / variabili d'ambiente

BRANDS = ["groomlyco", "magdock", "beffante"]

# Soglia di retention oltre la quale YouTube allarga la distribuzione.
# None = nessuna soglia documentata per quella durata (long-form).
SHORT_THRESHOLD = 65      # video fino a 30s
MEDIUM_THRESHOLD = 50     # video da 31 a 60s


def _service(brand_upper: str):
    creds = Credentials(
        token=None,
        refresh_token=os.environ[f"YOUTUBE_{brand_upper}_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ[f"YOUTUBE_{brand_upper}_CLIENT_ID"],
        client_secret=os.environ[f"YOUTUBE_{brand_upper}_CLIENT_SECRET"],
        scopes=[
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
        ],
    )
    return (
        build("youtube", "v3", credentials=creds),
        build("youtubeAnalytics", "v2", credentials=creds),
    )


def _duration_seconds(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "PT0S")
    h, mnt, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mnt * 60 + s


def _threshold(duration_s: int):
    if duration_s <= 30:
        return SHORT_THRESHOLD
    if duration_s <= 60:
        return MEDIUM_THRESHOLD
    return None


def check_brand(brand: str) -> None:
    brand_upper = brand.upper()
    if not os.environ.get(f"YOUTUBE_{brand_upper}_REFRESH_TOKEN"):
        print(f"\n=== {brand_upper}: credenziali assenti, salto ===")
        return

    try:
        yt, yta = _service(brand_upper)
        ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    except Exception as exc:
        print(f"\n=== {brand_upper}: ERRORE accesso API - {exc}")
        return

    stats = ch["statistics"]
    print(f"\n=== {ch['snippet']['title']} ===")
    print(f"Iscritti: {stats.get('subscriberCount')} | video: {stats.get('videoCount')} | views totali: {stats.get('viewCount')}")

    uploads_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    video_ids, page_token = [], None
    while True:
        resp = yt.playlistItems().list(
            part="contentDetails", playlistId=uploads_id, maxResults=50, pageToken=page_token
        ).execute()
        video_ids += [i["contentDetails"]["videoId"] for i in resp["items"]]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    meta = {}
    for i in range(0, len(video_ids), 50):
        resp = yt.videos().list(part="snippet,contentDetails", id=",".join(video_ids[i:i + 50])).execute()
        for v in resp["items"]:
            meta[v["id"]] = {
                "title": v["snippet"]["title"],
                "duration": _duration_seconds(v["contentDetails"]["duration"]),
            }

    try:
        rows = yta.reports().query(
            ids="channel==MINE",
            startDate="2020-01-01",
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="views,averageViewPercentage",
            dimensions="video",
            sort="-views",
            maxResults=200,
        ).execute().get("rows", [])
    except Exception as exc:
        print(f"  Analytics non disponibile ({exc}) - solo conteggio views sopra.")
        return

    if not rows:
        print("  Nessun dato Analytics ancora (canale troppo recente).")
        return

    passed, failed, longform = [], [], []
    for vid, views, pct in rows:
        m = meta.get(vid, {})
        dur = m.get("duration", 0)
        thresh = _threshold(dur)
        entry = (pct, views, dur, m.get("title", "?"), thresh)
        if thresh is None:
            longform.append(entry)
        elif pct >= thresh:
            passed.append(entry)
        else:
            failed.append(entry)

    print(f"\n  SUPERANO la soglia di retention ({len(passed)}):")
    for pct, views, dur, title, thresh in sorted(passed, reverse=True):
        print(f"    {pct:6.1f}% (>={thresh}%)  {views:6d}v  {dur:3d}s  {title[:55]}")

    print(f"\n  SOTTO la soglia ({len(failed)}):")
    for pct, views, dur, title, thresh in sorted(failed, reverse=True):
        print(f"    {pct:6.1f}% (< {thresh}%)  {views:6d}v  {dur:3d}s  {title[:55]}")

    if longform:
        print(f"\n  Long-form, nessuna soglia documentata ({len(longform)}):")
        for pct, views, dur, title, _ in sorted(longform, reverse=True):
            print(f"    {pct:6.1f}%          {views:6d}v  {dur:3d}s  {title[:55]}")

    valutati = len(passed) + len(failed)
    if valutati:
        print(f"\n  RIEPILOGO: {len(passed)}/{valutati} short superano la soglia "
              f"({len(passed) / valutati * 100:.0f}%).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", choices=BRANDS, help="un solo brand (default: tutti)")
    args = parser.parse_args()
    for brand in ([args.brand] if args.brand else BRANDS):
        check_brand(brand)


if __name__ == "__main__":
    main()
