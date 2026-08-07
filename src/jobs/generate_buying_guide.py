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
from datetime import datetime

from src.clients.cj_client import CJClient
from src.promo_scripts import (HOME_CLOSERS, HOME_RESOLUTIONS, PET_CLOSERS,
                               PET_RESOLUTIONS, SUBCATEGORY_PAYOFFS,
                               TECH_CLOSERS, TECH_RESOLUTIONS,
                               _detect_subcategory)
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
    "BEFFANTE": [
        "Top {n} Home Office & Smart Home Gadgets in 2026",
        "{n} Desk Setup Upgrades That Are Actually Worth It (2026)",
        "The {n} Home Tech Buys I Use Every Single Day (2026)",
        "{n} Smart Home Gadgets That Fixed Daily Annoyances (2026)",
        "{n} Home Office Gadgets You'll Wish You Bought Sooner (2026)",
    ],
}

NICHE_KEYWORDS = {
    "GROOMLYCO": ("dog", "cat", "pet", "paw", "puppy", "leash", "collar", "grooming", "nail", "feeder", "treat", "kennel", "harness"),
    "MAGDOCK": ("phone", "magsafe", "wireless", "charger", "car mount", "holder", "cable", "usb", "earbuds", "watch", "stand", "mount"),
    "BEFFANTE": ("projector", "webcam", "speaker", "smartwatch", "smart watch", "laptop", "power bank",
                 "security", "computer camera", "web camera", "beauty camera", "wifi camera", "home camera", "fill light"),
}

_ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh", "Eighth"]

# Brand -> codice nicchia usato da promo_scripts._detect_subcategory (PET/
# TECH/HOME), stessa mappa gia' invertita in src/jobs/daily_promo.py
# (BRAND_BY_NICHE) - qui serve nel verso opposto per passare la nicchia
# giusta al motore hook/payoff riusato da _segment_script sotto.
_BRAND_TO_NICHE = {"GROOMLYCO": "PET", "MAGDOCK": "TECH", "BEFFANTE": "HOME"}
_NICHE_DEFAULT_PAYOFFS = {"PET": PET_RESOLUTIONS, "TECH": TECH_RESOLUTIONS, "HOME": HOME_RESOLUTIONS}
_NICHE_CLOSERS = {"PET": PET_CLOSERS, "TECH": TECH_CLOSERS, "HOME": HOME_CLOSERS}


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


def _segment_script(rank: int, total: int, title: str, brand: str) -> str:
    """Numero + titolo (necessari per l'ordine della classifica), poi un
    payoff REALE - una spiegazione di meccanismo, non un placeholder - e una
    chiusura variata per nicchia.

    Bug trovato 2026-08-07 (routine di manutenzione). A differenza degli
    Shorts (src/promo_scripts.py, vedi il commento sopra SUBCATEGORY_PAYOFFS
    sullo stesso identico difetto gia' corretto li' il 2026-08-04), questo
    file non era mai stato collegato al motore hook/payoff per
    sottocategoria: OGNI segmento di OGNI buying guide, per tutti e tre i
    brand, chiudeva con la frase placeholder fissa "Here's why it's worth
    it. Look at the result." - la stessa promessa vuota mai pagata e la
    stessa chiusura identica su ogni video che promo_scripts.py chiama "uno
    dei segnali piu' riconoscibili di contenuto generato in serie".
    La ricerca 2026 (beautyshopcreators.com/tiktok-content-that-converts,
    consultata 2026-08-07) misura che i formati comparativi ("dupes",
    8.4-7.6%) battono l'haul/lista generica (2.3%) solo quando ogni voce
    porta una ragione concreta, non per la sola struttura a classifica -
    esattamente cio' che qui mancava.
    Riusa SUBCATEGORY_PAYOFFS/_detect_subcategory gia' scritti e verificati
    per gli Shorts, stesso pattern di riuso gia' in uso in
    src/jobs/daily_promo.py, invece di inventare nuove spiegazioni.
    """
    short_title = title.split(",")[0][:50]
    if rank == total:
        opener = f"And the number one pick: {short_title}."
    else:
        opener = f"Number {total - rank + 1}: {short_title}."
    niche = _BRAND_TO_NICHE.get(brand, "TECH")
    subcategory = _detect_subcategory(title, niche)
    payoff_pool = SUBCATEGORY_PAYOFFS.get(subcategory) or _NICHE_DEFAULT_PAYOFFS[niche]
    payoff = random.choice(payoff_pool)
    closer = random.choice(_NICHE_CLOSERS[niche])
    return f"{opener} {payoff} {closer}"


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
        script = _segment_script(i, n, p["title"], brand)
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
    "BEFFANTE": ["#homeoffice", "#desksetup", "#smarthome", "#techfinds",
                 "#gadgets", "#workfromhome", "#techtok", "#homegadgets"],
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
    from src.thumbnail import bake_thumbnail_card
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
    parser.add_argument("--brand", required=True, choices=["groomlyco", "magdock", "beffante"])
    parser.add_argument("-n", type=int, default=6, help="Quanti prodotti includere nella countdown")
    args = parser.parse_args()

    brand_upper = args.brand.upper()

    # Guardia credenziali PRIMA di generare (2026-08-04). Senza, un brand
    # non ancora collegato faceva tutto il lavoro pesante - chiamate CJ,
    # rendering di 6 segmenti video, concatenazione, diversi minuti di CPU -
    # per poi morire con KeyError sulla prima variabile d'ambiente mancante
    # al momento dell'upload. Stessa logica gia' presente in daily_promo.py.
    # Serve anche ai brand gia' attivi: se un token venisse revocato, meglio
    # accorgersene in due secondi che dopo un render completo.
    required = [f"YOUTUBE_{brand_upper}_CLIENT_ID",
                f"YOUTUBE_{brand_upper}_CLIENT_SECRET",
                f"YOUTUBE_{brand_upper}_REFRESH_TOKEN"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[{brand_upper}] credenziali YouTube mancanti ({', '.join(missing)}) - salto senza generare nulla.")
        raise SystemExit(0)

    # Guardia di partenza posticipata (2026-08-04). Bug reale evitato PRIMA
    # di pubblicare: questo script e' un job SEPARATO da daily_promo.py, che
    # ha gia' un posticipo esplicito per Beffante (richiesta utente: aspettare
    # fino a domani 15:00 prima della prima pubblicazione reale, per non far
    # sembrare l'account sospetto pubblicando subito dopo la creazione) - ma
    # generate_buying_guide.py non lo conosceva affatto. Il task
    # ShopifyBuyingGuideBeffante e' schedulato domani alle 11:20, quindi
    # SENZA questo controllo avrebbe pubblicato un video lungo 3h40 PRIMA del
    # limite voluto, aggirando il posticipo dall'altra porta. Importa la
    # stessa mappa da daily_promo.py invece di duplicare la data altrove: due
    # copie della stessa scadenza possono divergere.
    from src.jobs.daily_promo import BRAND_LAUNCH_AFTER
    launch_after = BRAND_LAUNCH_AFTER.get(brand_upper)
    if launch_after and datetime.now() < launch_after:
        print(f"[{brand_upper}] partira' alle {launch_after} - salto senza generare nulla per ora.")
        raise SystemExit(0)

    result = generate(brand_upper, args.n)
    if result:
        path, actual_n = result
        video_id = publish(brand_upper, path, actual_n)
        print(f"[OK] Buying guide pubblicata: video id={video_id}")
