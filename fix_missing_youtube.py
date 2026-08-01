"""
One-off: ricarica su YouTube i video generati da daily_promo.py che erano
gia' stati pubblicati su Instagram ma avevano fallito la pubblicazione
YouTube (log con 'youtube_error'), senza rigenerarli - i file .mp4 esistono
gia' in data/promo_videos/.
"""
import json
import os

from src.social.youtube_upload import upload_video

LOG_PATH = os.path.join(os.path.dirname(__file__), "data", "promo_content_log.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "promo_videos")


def main():
    with open(LOG_PATH, encoding="utf-8") as f:
        log = json.load(f)

    fixed = 0
    for entry in log:
        if not entry.get("youtube_error"):
            continue
        video_path = os.path.join(OUTPUT_DIR, f"{entry['video_id']}.mp4")
        if not os.path.exists(video_path):
            print(f"  ! {entry['video_id']}: file mancante, salto")
            continue
        try:
            title = f"{entry['title'].split(',')[0][:60]} #shorts"
            script = entry.get("script", entry["title"])
            youtube_id = upload_video(entry["brand"], video_path, title, script)
            entry["youtube_id"] = youtube_id
            del entry["youtube_error"]
            fixed += 1
        except Exception as exc:
            print(f"  ! {entry['video_id']}: fallito di nuovo: {exc}")

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
    print(f"\n{fixed} video corretti e pubblicati su YouTube.")


if __name__ == "__main__":
    main()
