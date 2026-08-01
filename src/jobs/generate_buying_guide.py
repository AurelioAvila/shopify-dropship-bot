"""
Job: genera un video "buying guide" long-form (8-10 min, non-Shorts) che
raggruppa N prodotti dello stesso brand in un'unica countdown, invece di un
prodotto solo come negli Shorts - target esplicito dell'utente 2026-07-31:
sbloccare un RPM/monetizzazione migliore con contenuto "normale" oltre agli
Shorts, stesso principio gia' applicato a xn0time/SoloFounded.

Ogni prodotto viene renderizzato come clip separata (build_promo_video,
stessa pipeline anti-blur degli Shorts) poi concatenate con ffmpeg in un
unico video verticale lungo, caricato su YouTube SENZA tag #shorts (quindi
trattato come video normale in base alla durata).

Uso:
    python -m src.jobs.generate_buying_guide --brand groomlyco
    python -m src.jobs.generate_buying_guide --brand magdock
"""
import argparse
import os
import random
import subprocess

from src.clients.cj_client import CJClient
from src.render_promo import build_promo_video
from src.social.youtube_upload import upload_video
from src.store import get_conn

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "buying_guides")

NICHE_TITLES = {
    "GROOMLYCO": "Top {n} Pet Grooming Must-Haves in 2026",
    "MAGDOCK": "Top {n} Phone & Car Accessories Worth Buying in 2026",
}

NICHE_KEYWORDS = {
    "GROOMLYCO": ("dog", "cat", "pet", "paw", "puppy", "leash", "collar", "grooming", "nail", "feeder", "treat", "kennel", "harness"),
    "MAGDOCK": ("phone", "magsafe", "wireless", "charger", "car mount", "holder", "cable", "usb", "earbuds", "watch", "stand", "mount"),
}

_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]


def _niche_products(cj: CJClient, conn, brand: str, n: int) -> list:
    keywords = NICHE_KEYWORDS[brand]
    pids = [r[0] for r in conn.execute("SELECT DISTINCT cj_pid FROM product_map").fetchall()]
    random.shuffle(pids)

    picked = []
    for pid in pids:
        if len(picked) >= n:
            break
        detail = cj.get_product_detail(pid)
        title = detail.get("productNameEn") or ""
        if not any(k in title.lower() for k in keywords):
            continue
        images = detail.get("productImageSet") or ([detail["bigImage"]] if detail.get("bigImage") else [])
        if not images:
            continue
        picked.append({"pid": pid, "title": title, "images": images[:6]})
    return picked


def _segment_script(rank: int, total: int, title: str) -> str:
    short_title = title.split(",")[0][:50]
    if rank == total:
        opener = f"And the number one pick: {short_title}."
    else:
        opener = f"Number {total - rank + 1}: {short_title}."
    return f"{opener} Here's why it's worth it. Look at the result."


def generate(brand: str, n: int = 6) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cj = CJClient()
    conn = get_conn()

    products = _niche_products(cj, conn, brand, n)
    conn.close()
    if len(products) < 3:
        print(f"  ! solo {len(products)} prodotti trovati per {brand}, servono almeno 3 - salto")
        return None

    clip_paths = []
    for i, p in enumerate(products, start=1):
        print(f"[{brand}] Genero segmento {i}/{len(products)}: {p['title'][:50]}...")
        script = _segment_script(i, len(products), p["title"])
        clip_path = os.path.join(OUTPUT_DIR, f"_segment_{brand}_{i}.mp4")
        tmp_dir = os.path.join(OUTPUT_DIR, f"_tmp_{brand}_{i}")
        build_promo_video(script, p["images"], clip_path, tmp_dir)
        clip_paths.append(clip_path)

    concat_list_path = os.path.join(OUTPUT_DIR, f"_concat_{brand}.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    output_path = os.path.join(OUTPUT_DIR, f"buying_guide_{brand.lower()}.mp4")
    print(f"[{brand}] Concateno {len(clip_paths)} segmenti in {output_path}...")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", output_path],
        check=True,
    )
    return output_path


def publish(brand: str, video_path: str, n_products: int) -> str:
    title = NICHE_TITLES[brand].format(n=n_products)
    description = (
        f"{title}\n\nShop the full collection - link in our bio.\n\n"
        + ("#petcare #doggrooming #petproducts" if brand == "GROOMLYCO" else "#techaccessories #phoneaccessories #caraccessories")
    )
    return upload_video(brand, video_path, title, description, tags=["petcare"] if brand == "GROOMLYCO" else ["techaccessories"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["groomlyco", "magdock"])
    parser.add_argument("-n", type=int, default=6, help="Quanti prodotti includere nella countdown")
    args = parser.parse_args()

    brand_upper = args.brand.upper()
    path = generate(brand_upper, args.n)
    if path:
        video_id = publish(brand_upper, path, args.n)
        print(f"[OK] Buying guide pubblicata: video id={video_id}")
