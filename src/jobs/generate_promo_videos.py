"""
Job 5: genera i video promozionali per i prodotti dello store, usando
le immagini reali dei prodotti (da CJ) + voce IA + sottotitoli automatici.

Uso:
    python -m src.jobs.generate_promo_videos
"""
import os

from src.clients.cj_client import CJClient
from src.render_promo import build_promo_video
from src.store import get_conn

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "promo_videos")

# product_title_match = sottostringa per trovare il prodotto giusto nel product_map
# (matchato sul titolo Shopify salvato quando abbiamo importato i prodotti)
SCRIPTS = [
    {
        "id": "1_nail_clipper_satisfying",
        "product_title_match": "Nail Clipper",
        "script": (
            "Il mio cane odiava il taglio delle unghie. "
            "Poi ho provato questo. "
            "Presa sicura, taglio netto, zero stress. "
            "Guarda il risultato."
        ),
    },
    {
        "id": "2_nail_trimmer_mythbust",
        "product_title_match": "Nail Trimmer",
        "script": (
            "Se il tuo cane scappa ogni volta che tiri fuori le forbici, "
            "probabilmente stai sbagliando la presa. "
            "Ecco il trucco: tieni la zampa cosi', "
            "taglia solo la punta bianca, mai il rosa. "
            "Fatto, in trenta secondi, senza stress per nessuno dei due."
        ),
    },
    {
        "id": "3_grooming_table",
        "product_title_match": "Grooming Table",
        "script": (
            "Se hai piu' di un cane, sai il caos di toelettarli su un tavolo normale. "
            "Questo cambia tutto: altezza regolabile, "
            "superficie antiscivolo, guinzaglio integrato. "
            "Tre cani, un pomeriggio, zero stress."
        ),
    },
    {
        "id": "4_magsafe_wallet_stresstest",
        "product_title_match": "Magsafe Magnetic Luxury",
        "script": (
            "Ti fidi davvero della calamita di questi portafogli magsafe? "
            "Io l'ho scosso, capovolto, e portato in tasca tutto il giorno. "
            "Non si e' staccato mai. "
            "Ecco perche' vale la spesa in piu' rispetto a uno normale."
        ),
    },
    {
        "id": "5_car_mount_comparison",
        "product_title_match": "Dashboard Car Phone Holder Mount Magnetic Stainless Steel",
        "script": (
            "La differenza tra un supporto auto economico e uno buono "
            "si vede solo quando e' troppo tardi, "
            "cioe' quando il telefono ti cade mentre guidi. "
            "Rotazione fluida, presa in acciaio, resistente all'acqua."
        ),
    },
    {
        "id": "6_car_mount_pov",
        "product_title_match": "Magnetic Bendable Car Mobile Phone Holder",
        "script": (
            "Pov: hai sempre il telefono che scivola nel portabicchieri "
            "mentre segui il navigatore. "
            "Installazione in cinque secondi. "
            "Fatto. Non lo stacco piu'."
        ),
    },
]


def generate_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cj = CJClient()
    conn = get_conn()

    for entry in SCRIPTS:
        pid, images = None, []
        for r in conn.execute("SELECT DISTINCT cj_pid FROM product_map").fetchall():
            detail = cj.get_product_detail(r[0])
            if entry["product_title_match"].lower() in (detail.get("productNameEn") or "").lower():
                pid = r[0]
                images = detail.get("productImageSet") or ([detail["bigImage"]] if detail.get("bigImage") else [])
                break

        if not pid or not images:
            print(f"  ! {entry['id']}: prodotto non trovato o senza immagini, salto")
            continue

        output_path = os.path.join(OUTPUT_DIR, f"{entry['id']}.mp4")
        tmp_dir = os.path.join(OUTPUT_DIR, f"_tmp_{entry['id']}")
        print(f"Genero {entry['id']}...")
        build_promo_video(entry["script"], images[:4], output_path, tmp_dir)
        print(f"  + salvato in {output_path}")

    conn.close()


if __name__ == "__main__":
    generate_all()
