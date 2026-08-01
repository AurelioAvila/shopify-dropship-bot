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
import time

from src.clients.cj_client import CJClient
from src.clients.shopify_client import ShopifyClient
from src.promo_scripts import build_caption_for_product, build_script_for_product
from src.render_promo import LowResolutionError, build_promo_video
from src.social.instagram_upload import upload_reel
from src.social.tiktok_upload import upload_video_to_inbox
from src.social.youtube_upload import upload_video as upload_youtube_video
from src.store import get_conn

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_videos")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_content_log.json")


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
    conn = get_conn()
    all_pids = [r[0] for r in conn.execute("SELECT DISTINCT cj_pid FROM product_map").fetchall()]
    conn.close()

    done_pids = {e["cj_pid"] for e in _load_log()}
    return [pid for pid in all_pids if pid not in done_pids]


def run(count: int = 2, skip_tiktok: bool = True, skip_instagram: bool = False, skip_youtube: bool = False) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cj = CJClient()
    shopify = ShopifyClient()

    candidates = _all_fresh_pids()
    if not candidates:
        print("Nessun prodotto nuovo da promuovere: tutto il catalogo e' gia' stato coperto.")
        print("Serve importare nuovi prodotti (src/jobs/import_products.py) per continuare.")
        return

    published = 0
    for pid in candidates:
        if published >= count:
            break

        detail = cj.get_product_detail(pid)
        title = detail.get("productNameEn") or "New product"
        images = detail.get("productImageSet") or ([detail["bigImage"]] if detail.get("bigImage") else [])
        if not images:
            print(f"  ! {pid} ({title}): nessuna immagine, salto")
            _append_log({"cj_pid": pid, "title": title, "skipped": "no_images"})
            continue

        script, niche = build_script_for_product(title)
        brand = "GROOMLYCO" if niche == "PET" else "MAGDOCK"
        video_id = f"auto-{int(time.time())}-{pid[-6:]}"
        output_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
        tmp_dir = os.path.join(OUTPUT_DIR, f"_tmp_{video_id}")

        print(f"[{brand}] Genero video per '{title}' ({pid})...")
        try:
            build_promo_video(script, images[:8], output_path, tmp_dir, niche=niche)
        except LowResolutionError as exc:
            # Standing quality bar (2026-08-01): mai pubblicare un Reel
            # visibilmente sfocato solo per rispettare la quota giornaliera -
            # si salta il prodotto e si passa al successivo, stesso standard
            # gia' garantito su CertSprint/PC Tweaker che usano footage stock
            # sempre nitido.
            print(f"  ! {pid} ({title}): {exc} - salto, cerco un prodotto con foto migliori")
            _append_log({"cj_pid": pid, "title": title, "skipped": "low_resolution"})
            continue

        caption = build_caption_for_product(title, niche)
        entry = {"cj_pid": pid, "title": title, "brand": brand, "video_id": video_id, "script": script}

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

        if not skip_youtube:
            yt_title = f"{caption.split('—')[0].strip()} #shorts"
            description = f"{script}\n\n{caption}"
            # "exceeded number of videos" e' spesso un rate-limit a burst
            # (visto risolversi da solo pochi minuti dopo nello stesso run),
            # non un tetto giornaliero fisso - un retry con pausa recupera
            # la maggior parte dei casi invece di segnarli come falliti.
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
            else:
                print(f"  ! YouTube fallito definitivamente per {video_id}: {last_exc}")
                entry["youtube_error"] = str(last_exc)

        # pausa tra un prodotto e l'altro per non fare burst di upload
        # ravvicinati su YouTube (causa probabile del rate-limit visto)
        time.sleep(20)

        _append_log(entry)
        published += 1
        print(f"  + fatto: {video_id}")

    if published < count:
        print(f"[WARN] pubblicati solo {published}/{count} oggi (candidati esauriti o scartati per bassa risoluzione).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=2, help="Quanti prodotti nuovi promuovere oggi")
    parser.add_argument("--only-tiktok", action="store_true")
    parser.add_argument("--with-tiktok", action="store_true", help="Prova anche TikTok (richiede token gia' generati per il brand)")
    parser.add_argument("--skip-youtube", action="store_true", help="Salta la pubblicazione YouTube (es. se i token per i brand non sono ancora pronti)")
    args = parser.parse_args()
    run(
        count=args.count,
        skip_tiktok=not (args.with_tiktok or args.only_tiktok),
        skip_instagram=args.only_tiktok,
        skip_youtube=args.only_tiktok or args.skip_youtube,
    )
