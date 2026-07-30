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
            "My dog used to hate nail trims. "
            "Then I tried this. "
            "Secure grip, clean cut, zero stress. "
            "Look at the result."
        ),
    },
    {
        "id": "2_nail_trimmer_mythbust",
        "product_title_match": "Nail Trimmer",
        "script": (
            "If your dog runs away every time you pull out the clippers, "
            "you're probably holding it wrong. "
            "Here's the trick: hold the paw like this, "
            "only cut the white tip, never the pink. "
            "Done, in thirty seconds, stress-free for both of you."
        ),
    },
    {
        "id": "3_grooming_table",
        "product_title_match": "Grooming Table",
        "script": (
            "If you have more than one dog, you know the chaos of grooming them on a normal table. "
            "This changes everything: adjustable height, "
            "non-slip surface, built-in leash arm. "
            "Three dogs, one afternoon, zero stress."
        ),
    },
    {
        "id": "4_magsafe_wallet_stresstest",
        "product_title_match": "Magsafe Magnetic Luxury",
        "script": (
            "Do you actually trust the magnet on these MagSafe wallets? "
            "I shook it, flipped it upside down, and carried it in my pocket all day. "
            "It never fell off. "
            "That's why it's worth the extra couple of euros over a regular case."
        ),
    },
    {
        "id": "5_car_mount_comparison",
        "product_title_match": "Dashboard Car Phone Holder Mount Magnetic Stainless Steel",
        "script": (
            "The difference between a cheap car mount and a good one "
            "only shows up when it's too late, "
            "meaning when your phone drops while you're driving. "
            "Smooth rotation, steel grip, water resistant."
        ),
    },
    {
        "id": "6_car_mount_pov",
        "product_title_match": "Magnetic Bendable Car Mobile Phone Holder",
        "script": (
            "POV: your phone keeps sliding in the cup holder "
            "while you're following the GPS. "
            "Five second install. "
            "Done. Never taking it off."
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
        build_promo_video(entry["script"], images[:8], output_path, tmp_dir)
        print(f"  + salvato in {output_path}")

    conn.close()


if __name__ == "__main__":
    generate_all()
