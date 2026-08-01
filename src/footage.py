"""
Searches and downloads free vertical background video from Pexels.
Requires PEXELS_API_KEY. Ported from certsprint-reels-bot 2026-08-01: used
here as the backdrop behind product cutouts instead of a blurred copy of
the (often low-res, plain-white-background) product photo itself - real
moving lifestyle b-roll behind a sharp product looks alive, a blurred
studio photo does not, no matter how much saturation/contrast is applied.
"""
import os
import random
import requests

TARGET_RATIO = 9 / 16


def download_background_video(output_path: str, query: str) -> str:
    api_key = os.environ["PEXELS_API_KEY"]

    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "per_page": 20},
        timeout=30,
    )
    resp.raise_for_status()
    results = resp.json().get("videos", [])
    if not results:
        raise RuntimeError(f"No Pexels videos found for query '{query}'")

    def _aspect_diff(v):
        w, h = v.get("width") or 1, v.get("height") or 1
        return abs((w / h) - TARGET_RATIO)

    results.sort(key=_aspect_diff)
    top_candidates = results[: max(1, len(results) // 3)]
    video = random.choice(top_candidates)

    files = sorted(video["video_files"], key=lambda f: abs((f.get("height") or 0) - 1920))
    video_url = files[0]["link"]

    video_resp = requests.get(video_url, timeout=60, stream=True)
    video_resp.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in video_resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return output_path
