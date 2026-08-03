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
from src.render_promo import LowResolutionError, build_promo_video
from src.social.youtube_upload import upload_video
from src.store import get_conn
from src.thumbnail import build_thumbnail

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "buying_guides")

# Pool di titoli invece di un template unico (fix 2026-08-02): prima era una
# sola stringa per brand e `-n` ha default 6, quindi OGNI buying guide usciva
# col titolo IDENTICO ("Top 6 Pet Grooming Must-Haves in 2026"). Su un canale
# YouTube titoli duplicati si cannibalizzano nella ricerca e non danno a chi
# scorre nessun motivo per cliccare il nuovo invece del vecchio. Le varianti
# puntano su curiosita'/beneficio ("che ho ricomprato", "che valgono davvero")
# invece del semplice elenco, coerente col dato che gli hook con conseguenza
# battono quelli generici (vedi feedback_reinforce_winning_hooks).
NICHE_TITLES = {
    "GROOMLYCO": [
        "Top {n} Pet Grooming Must-Haves in 2026",
        "{n} Dog Grooming Tools That Actually Last (2026)",
        "The {n} Pet Products I'd Buy Again in 2026",
        "{n} Things Every Dog Owner Should Own (2026)",
        "{n} Pet Grooming Upgrades Worth The Money in 2026",
    ],
    "MAGDOCK": [
        "Top {n} Phone & Car Accessories Worth Buying in 2026",
        "{n} Phone Accessories That Are Actually Worth It (2026)",
        "The {n} Tech Buys I Use Every Single Day (2026)",
        "{n} Car & Phone Upgrades That Fixed Daily Annoyances (2026)",
        "{n} Phone Accessories You'll Wish You Bought Sooner (2026)",
    ],
}

NICHE_KEYWORDS = {
    "GROOMLYCO": ("dog", "cat", "pet", "paw", "puppy", "leash", "collar", "grooming", "nail", "feeder", "treat", "kennel", "harness"),
    "MAGDOCK": ("phone", "magsafe", "wireless", "charger", "car mount", "holder", "cable", "usb", "earbuds", "watch", "stand", "mount"),
}

_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]


def _niche_products(cj: CJClient, conn, brand: str, n: int) -> list:
    # Sovra-pesca candidati (n*3): alcuni verranno scartati in generate()
    # per bassa risoluzione immagine, serve un margine per arrivare comunque
    # a n segmenti buoni senza far fallire l'intero video.
    keywords = NICHE_KEYWORDS[brand]
    pids = [r[0] for r in conn.execute("SELECT DISTINCT cj_pid FROM product_map").fetchall()]
    random.shuffle(pids)

    picked = []
    for pid in pids:
        if len(picked) >= n * 3:
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

    candidates = _niche_products(cj, conn, brand, n)
    conn.close()
    if len(candidates) < 3:
        print(f"  ! solo {len(candidates)} prodotti trovati per {brand}, servono almeno 3 - salto")
        return None

    # Un prodotto con immagini a bassa risoluzione non deve far fallire
    # l'intero video (bug reale visto il 2026-08-01: LowResolutionError non
    # catturato mandava in crash l'intera generazione, perdendo anche i
    # segmenti gia' renderizzati) - si salta e si passa al candidato dopo.
    used_products = []
    clip_paths = []
    for p in candidates:
        if len(used_products) >= n:
            break
        i = len(used_products) + 1
        print(f"[{brand}] Genero segmento {i}/{n}: {p['title'][:50]}...")
        script = _segment_script(i, n, p["title"])
        clip_path = os.path.join(OUTPUT_DIR, f"_segment_{brand}_{i}.mp4")
        tmp_dir = os.path.join(OUTPUT_DIR, f"_tmp_{brand}_{i}")
        try:
            build_promo_video(script, p["images"], clip_path, tmp_dir)
        except LowResolutionError as exc:
            print(f"  ! {p['title'][:50]}: risoluzione troppo bassa, salto ({exc})")
            continue
        clip_paths.append(clip_path)
        used_products.append(p)

    if len(clip_paths) < 3:
        print(f"  ! solo {len(clip_paths)} segmenti validi per {brand} (troppi scarti per bassa risoluzione), servono almeno 3 - salto")
        return None

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
    return output_path, len(clip_paths)


TAG_POOLS = {
    "GROOMLYCO": ["#petcare", "#doggrooming", "#petproducts", "#dogsoftiktok",
                  "#puppylove", "#petmusthaves", "#dogmom", "#petaccessories"],
    "MAGDOCK": ["#techaccessories", "#phoneaccessories", "#caraccessories",
                "#techtok", "#lifehack", "#gadgets", "#magsafe", "#deskaesthetic"],
}


def publish(brand: str, video_path: str, n_products: int) -> str:
    title = random.choice(NICHE_TITLES[brand]).format(n=n_products)
    # Prima erano sempre gli stessi 3 hashtag identici su ogni video - stesso
    # tag pool statico non rinnovato = look ripetitivo/spam agli occhi
    # dell'algoritmo. Ora pesca un sottoinsieme casuale, stesso principio gia'
    # in uso per gli Shorts giornalieri (src/promo_scripts.py).
    tags = " ".join(random.sample(TAG_POOLS[brand], 4))
    description = f"{title}\n\nShop the full collection - link in our bio.\n\n{tags}"

    # Miniatura col titolo in grande: su un long-form e' LA leva del click,
    # e senza YouTube ne sceglieva una da un fotogramma a caso (tipicamente
    # meta' di una parola dei sottotitoli). Se la generazione fallisce si
    # pubblica lo stesso con quella automatica.
    thumbnail_path = None
    try:
        thumbnail_path = build_thumbnail(
            title,
            os.path.join(OUTPUT_DIR, f"thumb_{brand.lower()}.jpg"),
            video_path=video_path,
            brand=brand,
        )
    except Exception as exc:
        print(f"  ! miniatura non generata ({exc}) - si prosegue senza")

    # Groomlyco e Magdock non hanno il telefono verificato (confermato
    # 2026-08-03, l'API rifiuta sempre thumbnails.set con 403) - upload_video
    # tenta comunque via API (gratis, senza rischio, funziona da solo se il
    # canale viene verificato in futuro), ma nel frattempo brucia lo stesso
    # design nei primi secondi del video: qualunque fotogramma YouTube scelga
    # come copertina automatica in quella finestra E' il design voluto.
    from thumbnail import bake_thumbnail_card
    try:
        bake_thumbnail_card(video_path, title, brand=brand)
    except Exception as exc:
        print(f"  ! card iniziale non bruciata ({exc}) - si prosegue senza")

    # I tag dell'API sono un canale diverso dagli hashtag visibili: qui vanno
    # senza '#' e conviene usarli tutti (il campo regge ~500 caratteri), non
    # solo i primi due.
    api_tags = [t.lstrip("#") for t in TAG_POOLS[brand]]
    return upload_video(brand, video_path, title, description, tags=api_tags,
                        thumbnail_path=thumbnail_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=["groomlyco", "magdock"])
    parser.add_argument("-n", type=int, default=6, help="Quanti prodotti includere nella countdown")
    args = parser.parse_args()

    brand_upper = args.brand.upper()
    result = generate(brand_upper, args.n)
    if result:
        path, actual_n = result
        video_id = publish(brand_upper, path, actual_n)
        print(f"[OK] Buying guide pubblicata: video id={video_id}")
