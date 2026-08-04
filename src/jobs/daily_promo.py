"""
Job giornaliero: sceglie N prodotti del catalogo (product_map) non ancora
promossi, genera lo script (src/promo_scripts.py), renderizza il video
(render_promo.build_promo_video, stessa pipeline anti-blur usata per i
primi 8 video) e pubblica su Instagram + TikTok del brand giusto
(Groomlyco per pet, Magdock per tech). Tiene un log persistente
(data/promo_content_log.json) per non ripromuovere due volte lo stesso
prodotto.

Priorita' esplicita dell'utente: il contenuto deve sempre reindirizzare
i clienti allo store Shopify (CTA "link in bio" su ogni video), ma il
gancio/hook puo' vertere su un problema/consiglio della nicchia (pet care
o tech accessori) invece che essere un annuncio prodotto diretto - vedi
src/promo_scripts.py per gli hook.

Uso:
    python -m src.jobs.daily_promo --count 2
"""
import argparse
import json
import os
import re
import time
from datetime import datetime

from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.promo_scripts import (_detect_subcategory, build_caption_for_product,
                               build_script_for_product, build_youtube_title,
                               shorten_product_name)
from src.render_promo import LowResolutionError, build_promo_video
from src.social.instagram_upload import upload_reel
from src.social.tiktok_upload import upload_video_to_inbox
from src.social.youtube_upload import upload_video as upload_youtube_video
from src.store import get_conn

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_videos")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_content_log.json")

# Terzo brand (Beffante, tech da casa/scrivania) aggiunto 2026-08-03.
# Il rilevamento nicchia di promo_scripts.py ora e' a tre valori
# (PET/TECH/HOME) e instrada da solo sul brand giusto, quindi il blocco
# temporaneo che saltava questi prodotti non serve piu': la lista di parole
# chiave vive solo in promo_scripts.HOME_KEYWORDS, per non tenerne due copie
# che possono divergere.
BRAND_BY_NICHE = {
    "PET": "GROOMLYCO",
    "TECH": "MAGDOCK",
    "HOME": "BEFFANTE",
}
NICHE_BY_BRAND = {brand: niche for niche, brand in BRAND_BY_NICHE.items()}

# Vedi commento sulla guardia di partenza posticipata qui sotto in run().
BRAND_LAUNCH_AFTER = {
    "BEFFANTE": datetime(2026, 8, 4, 15, 0),
}


def _now() -> datetime:
    return datetime.now()


def _load_log() -> list:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        return json.load(f)


def _append_log(entry: dict) -> None:
    log = _load_log()
    log.append(entry)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def _all_fresh_pids() -> list:
    """Prodotti non ancora promossi, in ordine FIFO puro (vecchio comportamento,
    tenuto come fallback - vedi _all_fresh_pids_fair sotto per quello usato
    davvero)."""
    conn = get_conn()
    all_pids = [r[0] for r in conn.execute("SELECT DISTINCT cj_pid FROM product_map").fetchall()]
    conn.close()

    done_pids = {e["cj_pid"] for e in _load_log()}
    return [pid for pid in all_pids if pid not in done_pids]


def _pid_to_brand_map(with_titles: bool = False) -> dict:
    """cj_pid -> vendor Shopify (Groomlyco/Magdock/Beffante), con UNA sola
    chiamata Shopify (list_products, tutto il catalogo in una pagina) invece
    di richiedere il dettaglio CJ per ogni singolo pid - quello e' gia' il
    passo lento/rate-limitato che il resto del job fa dopo, per i soli
    candidati davvero scelti.

    Con with_titles=True torna cj_pid -> (vendor, titolo): il titolo serve a
    _pick_for_brand per riconoscere i prodotti quasi identici, e viene dalla
    stessa risposta Shopify - nessuna chiamata in piu'."""
    try:
        shopify = ShopifyClient()
        products = shopify.list_products()
    except Exception as exc:
        print(f"  ! impossibile leggere i vendor da Shopify ({exc}) - ordine FIFO come fallback")
        return {}

    by_shopify_id = {str(p["id"]): (p.get("vendor", "?"), p.get("title", "")) for p in products}

    conn = get_conn()
    rows = conn.execute("SELECT cj_pid, shopify_product_id FROM product_map").fetchall()
    conn.close()
    out = {}
    for cj_pid, shopify_id in rows:
        vendor, title = by_shopify_id.get(str(shopify_id), ("?", ""))
        out[cj_pid] = (vendor, title) if with_titles else vendor
    return out


def _product_signature(title: str, brand: str) -> str:
    """Firma grossolana di "che tipo di oggetto e'", per non pubblicare due
    prodotti quasi identici uno dietro l'altro.

    Prima la sottocategoria nota; se il prodotto non ne ha una, le prime due
    parole significative del nome ("Mini Projector", "Wireless Camera") - che
    su questo catalogo bastano a distinguere un proiettore da una webcam.
    """
    sub = _detect_subcategory(title, NICHE_BY_BRAND.get(brand, "TECH"))
    if sub:
        return sub
    short = shorten_product_name(title, 2)
    return short.lower() or "?"


def _fresh_pids_by_brand() -> dict:
    """Prodotti non ancora promossi, raggruppati per brand (vendor Shopify).

    Normalizzato a maiuscolo (2026-08-04): il vendor Shopify e' "Groomlyco"/
    "Magdock"/"Beffante", ma BRAND_BY_NICHE e il "brand" nel log usano sempre
    le chiavi maiuscole - senza .upper() qui, _pick_for_brand non trovava mai
    candidati freschi (chiave sbagliata) e ricadeva sempre sul riciclo anche
    con scorte piene, bug scoperto testando questa stessa funzione.
    """
    fifo = _all_fresh_pids()
    meta_of = _pid_to_brand_map(with_titles=True)
    by_brand = {}
    for pid in fifo:
        vendor, title = meta_of.get(pid, ("?", ""))
        by_brand.setdefault(vendor.upper(), []).append((pid, title))
    return by_brand


def _promoted_pids_by_brand() -> dict:
    """Prodotti gia' promossi con successo, raggruppati per brand e ordinati
    dal meno recentemente ripubblicato (per il riciclo, vedi _pick_for_brand).
    Il timestamp viene letto dal video_id (auto-<unix_ts>-<pid>), non serve
    un campo dedicato nel log."""
    by_brand = {}
    for e in _load_log():
        brand, pid, vid = e.get("brand"), e.get("cj_pid"), e.get("video_id", "")
        if not brand or not pid or e.get("skipped"):
            continue
        m = re.match(r"auto-(\d+)-", vid)
        ts = int(m.group(1)) if m else 0
        by_brand.setdefault(brand, []).append((ts, pid))
    for brand in by_brand:
        by_brand[brand].sort()
    return by_brand


def _recent_signatures(brand: str, depth: int = 3) -> set:
    """Firme dei prodotti pubblicati piu' di recente per questo brand, in modo
    che il prossimo non sia l'ennesimo oggetto dello stesso tipo."""
    entries = []
    for e in _load_log():
        if e.get("brand") != brand or e.get("skipped") or not e.get("title"):
            continue
        m = re.match(r"auto-(\d+)-", e.get("video_id", ""))
        entries.append((int(m.group(1)) if m else 0, e["title"]))
    entries.sort(reverse=True)
    return {_product_signature(t, brand) for _, t in entries[:depth]}


def _pick_for_brand(brand: str, fresh_by_brand: dict, promoted_by_brand: dict,
                    avoid_signatures: set = None):
    """Un candidato per questo brand, indipendentemente dagli altri brand.

    PERCHE' ESISTE (2026-08-04): con un'unica lista interlacciata globale e
    count=1/run, il ciclo si fermava al primo candidato utile - cioe' sempre
    lo stesso brand per run intere consecutive, finche' il suo blocco di
    prodotti "freschi" (importati a lotti per brand, quindi vicini in ID CJ)
    non si esauriva. Verificato: Magdock silenzioso 12+ ore mentre Groomlyco
    pubblicava 2 volte, pur avendo Magdock PIU' prodotti freschi (30 vs 24).

    Ogni brand ora sceglie il proprio candidato per conto suo: prima tra i
    prodotti mai promossi, poi - se esauriti - ricicla il proprio prodotto
    gia' promosso da piu' tempo, cosi' un brand non pubblica mai zero volte
    solo perche' un altro brand ha ancora scorte fresche o ne ha meno.
    """
    fresh = fresh_by_brand.get(brand) or []
    if fresh:
        # FIFO puro, ma saltando i prodotti dello stesso tipo appena
        # pubblicati (2026-08-04). I prodotti si importano a lotti per
        # categoria, quindi in ordine di cj_pid escono vicini: Beffante ha
        # aperto il canale con 3 PROIETTORI su 4 promo, due dei quali con lo
        # stesso identico hook - un canale nuovo che si presenta cosi' sembra
        # un feed duplicato, che e' esattamente cio' che si e' gia' deciso di
        # non fare sulle copertine.
        for i, (pid, title) in enumerate(fresh):
            sig = _product_signature(title, brand)
            if sig not in (avoid_signatures or set()):
                fresh.pop(i)
                # La scelta entra subito fra quelle da evitare, cosi' anche una
                # run con count>1 non pubblica due volte lo stesso tipo.
                if avoid_signatures is not None:
                    avoid_signatures.add(sig)
                return pid, False
        # Tutti i freschi rimasti sono dello stesso tipo dei recenti: si
        # pubblica comunque, meglio un doppione che un giorno di silenzio.
        return fresh.pop(0)[0], False
    promoted = promoted_by_brand.get(brand) or []
    if promoted:
        return promoted.pop(0)[1], True
    return None, False


def run(count: int = 2, skip_tiktok: bool = False, skip_instagram: bool = False, skip_youtube: bool = False,
        youtube_limit: int = 3) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cj = CJClient()
    shopify = ShopifyClient()

    fresh_by_brand = _fresh_pids_by_brand()
    promoted_by_brand = _promoted_pids_by_brand()
    if not any(fresh_by_brand.values()) and not any(promoted_by_brand.values()):
        print("Nessun prodotto da promuovere: catalogo vuoto per tutti i brand.")
        print("Serve importare nuovi prodotti (src/jobs/import_products.py) per continuare.")
        return

    published = 0
    youtube_uploaded = 0
    # Ogni brand e' indipendente dagli altri (2026-08-04, vedi _pick_for_brand):
    # gira il suo turno anche se un altro brand non ha piu' prodotti freschi o
    # non ha ancora pubblicato in questa run.
    for target_brand in ("GROOMLYCO", "MAGDOCK", "BEFFANTE"):
        # Partenza posticipata per brand (2026-08-03): richiesta esplicita
        # dell'utente per Beffante, appena collegato - vuole aspettare fino a
        # domani 15:00 prima della prima pubblicazione reale, per non farlo
        # bannare partendo subito a raffica lo stesso giorno del collegamento
        # account.
        launch_after = BRAND_LAUNCH_AFTER.get(target_brand)
        if launch_after and _now() < launch_after:
            print(f"  - {target_brand}: partira' alle {launch_after}, salto per ora")
            continue

        # Guardia 2026-08-04: Beffante (3o brand) non ha ancora credenziali
        # social configurate (account creati ma token non ancora collegati).
        if not os.environ.get(f"INSTAGRAM_{target_brand}_ACCESS_TOKEN") and not os.environ.get(f"TIKTOK_{target_brand}_CLIENT_KEY"):
            print(f"  - {target_brand}: senza credenziali social ancora, salto per ora")
            continue

        brand_published = 0
        attempts = 0
        avoid = _recent_signatures(target_brand)
        while brand_published < count and attempts < 8:
            attempts += 1
            pid, recycled = _pick_for_brand(target_brand, fresh_by_brand,
                                            promoted_by_brand, avoid)
            if pid is None:
                print(f"  ! {target_brand}: nessun prodotto disponibile (nemmeno da riciclare), salto")
                break

            detail = cj.get_product_detail(pid)
            title = detail.get("productNameEn") or "New product"

            images = detail.get("productImageSet") or ([detail["bigImage"]] if detail.get("bigImage") else [])
            if not images:
                print(f"  ! {pid} ({title}): nessuna immagine, salto")
                if not recycled:
                    _append_log({"cj_pid": pid, "title": title, "skipped": "no_images"})
                continue

            # La nicchia viene dal BRAND del prodotto (vendor Shopify, dato
            # curato a mano), non riindovinata dal titolo CJ.
            #
            # Bug reale corretto qui il 2026-08-04: il prodotto era gia' stato
            # scelto dentro il turno di target_brand, ma queste due righe
            # ricalcolavano il brand dal titolo e potevano ribaltarlo. Con il
            # ripiego casuale che c'era in _detect_niche, un accessorio da auto
            # senza keyword note finiva in PET una volta su due e veniva
            # pubblicato su GROOMLYCO con un voiceover sui cani sopra le foto
            # del prodotto. Verificato sui video gia' online: "Mini GPS Tracker
            # Strong Magnetic Mount Car Motorcycle Truck" e "Motorcycle
            # electric vehicle positioning tracker" stanno sul canale pet, con
            # hook "This is the mistake almost every dog owner makes" e
            # "Nobody tells you this before you get [a dog]". Oltre a bruciare
            # il prodotto sul pubblico sbagliato, questo rendeva inutile la
            # rotazione per brand: il turno di MAGDOCK poteva pubblicare su
            # GROOMLYCO.
            brand = target_brand
            # value_first (2026-08-04): 4 video su 5 non spingono il negozio -
            # vedi VALUE_FIRST_PROBABILITY in promo_scripts. Va passato alla
            # caption perche' testo e voiceover devono dire la stessa cosa.
            script, niche, hook, value_first = build_script_for_product(title, niche=NICHE_BY_BRAND[brand])

            video_id = f"auto-{int(time.time())}-{pid[-6:]}"
            output_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
            tmp_dir = os.path.join(OUTPUT_DIR, f"_tmp_{video_id}")

            tag = "RICICLO - " if recycled else ""
            print(f"[{brand}] {tag}Genero video per '{title}' ({pid})...")
            try:
                build_promo_video(script, images[:8], output_path, tmp_dir, niche=niche, hook=hook)
            except LowResolutionError as exc:
                # Standing quality bar (2026-08-01): mai pubblicare un Reel
                # visibilmente sfocato solo per rispettare la quota giornaliera -
                # si salta il prodotto e si passa al successivo, stesso standard
                # gia' garantito su CertSprint/PC Tweaker che usano footage stock
                # sempre nitido.
                print(f"  ! {pid} ({title}): {exc} - salto, cerco un prodotto con foto migliori")
                if not recycled:
                    _append_log({"cj_pid": pid, "title": title, "skipped": "low_resolution"})
                continue

            caption = build_caption_for_product(title, niche, hook, value_first=value_first)
            entry = {"cj_pid": pid, "title": title, "brand": brand, "video_id": video_id, "script": script}
            if recycled:
                entry["recycled"] = True

            if not skip_tiktok:
                try:
                    # In attesa dell'audit "Direct Post" mandiamo il video nelle
                    # bozze ("Upload to TikTok") invece di pubblicarlo
                    # direttamente - funziona gia' oggi senza restrizione
                    # SELF_ONLY. La caption va incollata a mano (l'endpoint
                    # bozze non la accetta via API), la salviamo accanto al
                    # video e la mandiamo anche su Telegram per averla sul telefono.
                    upload_video_to_inbox(brand, output_path, caption=caption)
                    caption_path = output_path.replace(".mp4", "_tiktok_caption.txt")
                    with open(caption_path, "w", encoding="utf-8") as f:
                        f.write(caption)
                    entry["tiktok"] = "ok (bozza)"
                except Exception as exc:
                    print(f"  ! TikTok fallito per {video_id}: {exc}")
                    entry["tiktok"] = f"error: {exc}"

            if not skip_instagram:
                try:
                    public_url = shopify.upload_video_get_public_url(output_path, alt=video_id)
                    media_id = upload_reel(brand, public_url, caption)
                    entry["instagram_media_id"] = media_id
                except Exception as exc:
                    print(f"  ! Instagram fallito per {video_id}: {exc}")
                    entry["instagram_error"] = str(exc)

            # Credenziali YouTube specifiche del brand, controllate PRIMA del
            # retry loop (2026-08-04). Bug reale: youtube_uploaded si incrementa
            # solo sui successi, quindi se il brand non ha le credenziali YouTube
            # (es. Beffante appena sbloccato su TikTok ma non ancora su YouTube)
            # "youtube_uploaded < youtube_limit" resta vero per sempre e OGNI
            # prodotto della run tentava 3 volte con 90s di pausa tra un
            # tentativo e l'altro - fino a 180s sprecati per prodotto, ad ogni
            # run (6 volte al giorno), su un KeyError immediato che nessun retry
            # puo' risolvere. Il retry ha senso per errori di quota/rete
            # transitori (per cui e' nato), non per credenziali mancanti.
            has_youtube_creds = all(os.environ.get(f"YOUTUBE_{brand}_{k}") for k in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN"))
            if not skip_youtube and not has_youtube_creds:
                # if/elif/elif unico, non due if separati (2026-08-04): con due
                # if indipendenti l'elif del ramo "limite raggiunto" piu' sotto si
                # legava comunque a questo caso, stampando ANCHE un messaggio
                # sbagliato ("limite di N/run gia' raggiunto") quando il vero
                # motivo era l'assenza di credenziali - trovato rileggendo la
                # catena invece di fidarmi che l'aggiunta fosse isolata.
                print(f"  - YouTube: {brand} senza credenziali YouTube ancora - salto senza ritentare (resta su TikTok/Instagram)")
            elif not skip_youtube and has_youtube_creds and youtube_uploaded < youtube_limit:
                # Costruito dall'HOOK e con "#shorts" garantito entro i 100
                # caratteri: prima partiva dalla caption intera (CTA + hashtag
                # Instagram inclusi), arrivava a 130-187 caratteri, YouTube
                # troncava a 100 e "#shorts" spariva - verificato sul video
                # pubblicato _JQ5J6ktUDs. Vedi build_youtube_title.
                # Il nome prodotto entra nel titolo: senza, uscivano titoli come
                # "Try it once and you'll see. #shorts", cioe' senza una sola
                # parola cercabile su YouTube. Vedi build_youtube_title.
                yt_title = build_youtube_title(hook, product_name=title)
                description = f"{script}\n\n{caption}"
                # I progetti OAuth non ancora verificati da Google hanno una quota
                # giornaliera di upload video molto bassa (uploadLimitExceeded) -
                # confermato live 2026-08-01: 3 tentativi con pausa di 90s NON la
                # aggirano quando la quota e' davvero esaurita (a differenza di un
                # rate-limit a burst). Per questo motivo limitiamo gli upload
                # YouTube per run (youtube_limit) invece di ritentare all'infinito
                # su ogni prodotto - IG e TikTok non hanno questa restrizione e
                # restano quindi il canale principale finche' l'app non viene
                # verificata da Google.
                last_exc = None
                youtube_id = None
                for attempt in range(3):
                    try:
                        youtube_id = upload_youtube_video(brand, output_path, yt_title, description)
                        break
                    except Exception as exc:
                        last_exc = exc
                        if attempt < 2:
                            print(f"  ! YouTube fallito per {video_id} (tentativo {attempt + 1}/3), riprovo tra 90s: {exc}")
                            time.sleep(90)
                if youtube_id:
                    entry["youtube_id"] = youtube_id
                    youtube_uploaded += 1
                else:
                    print(f"  ! YouTube fallito definitivamente per {video_id}: {last_exc}")
                    entry["youtube_error"] = str(last_exc)
            elif not skip_youtube:
                print(f"  - YouTube: limite di {youtube_limit}/run gia' raggiunto, salto per {video_id} (resta su IG/TikTok)")

            # Robustezza (2026-08-04, in vista dell'attivazione di Beffante con
            # credenziali social nuove/eventualmente incomplete): prima, se TUTTE
            # le piattaforme fallivano (es. una env var mancante o un token non
            # ancora valido), il prodotto veniva comunque segnato "promosso" nel
            # log e non veniva mai piu' ritentato - un brand con credenziali rotte
            # avrebbe silenziosamente bruciato l'intero catalogo pubblicando zero
            # contenuti. Ora si consuma il prodotto solo se e' stato pubblicato
            # davvero da almeno una piattaforma tra quelle NON esplicitamente
            # saltate (skip_* e' un dry-run intenzionale, non un fallimento).
            attempted = not (skip_tiktok and skip_instagram and skip_youtube)
            any_success = (
                (not skip_tiktok and entry.get("tiktok") == "ok (bozza)")
                or (not skip_instagram and "instagram_media_id" in entry)
                or (not skip_youtube and "youtube_id" in entry)
            )
            if attempted and not any_success:
                print(f"  ! {pid} ({title}): fallito su TUTTE le piattaforme tentate - riprovo con un altro prodotto {target_brand}")
                time.sleep(20)
                continue

            # pausa tra un prodotto e l'altro per non fare burst di upload
            # ravvicinati su YouTube (causa probabile del rate-limit visto)
            time.sleep(20)

            _append_log(entry)
            published += 1
            brand_published += 1
            print(f"  + fatto: {video_id}")

        if brand_published == 0:
            print(f"[WARN] {target_brand}: nessuna pubblicazione riuscita in questa run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=2, help="Quanti prodotti nuovi promuovere oggi")
    parser.add_argument("--only-tiktok", action="store_true")
    parser.add_argument("--skip-tiktok", action="store_true", help="Salta TikTok (es. se i token per il brand non sono pronti)")
    parser.add_argument("--skip-youtube", action="store_true", help="Salta la pubblicazione YouTube (es. se i token per i brand non sono ancora pronti)")
    args = parser.parse_args()
    run(
        count=args.count,
        skip_tiktok=args.skip_tiktok,
        skip_instagram=args.only_tiktok,
        skip_youtube=args.only_tiktok or args.skip_youtube,
    )
