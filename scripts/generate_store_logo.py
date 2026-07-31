"""
Genera un logo neutro per lo store (icona semplice, nessun nome brand
specifico, cosi' funziona indipendentemente dal dominio scelto).

Uso: python scripts/generate_store_logo.py
"""
import os

from PIL import Image, ImageDraw

SIZE = 512
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "branding", "store_logo.png")


def make_logo() -> None:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = (30, 33, 43)
    accent = (64, 156, 255)

    margin = int(SIZE * 0.08)
    draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=int(SIZE * 0.18), fill=bg_color)

    # Semplice icona "sacchetto della spesa" stilizzata
    bag_w, bag_h = SIZE * 0.42, SIZE * 0.36
    bag_x, bag_y = (SIZE - bag_w) / 2, SIZE * 0.36
    draw.rounded_rectangle(
        [bag_x, bag_y, bag_x + bag_w, bag_y + bag_h], radius=int(SIZE * 0.03), fill=(255, 255, 255)
    )
    handle_w = bag_w * 0.5
    handle_x = bag_x + (bag_w - handle_w) / 2
    draw.arc(
        [handle_x, bag_y - SIZE * 0.12, handle_x + handle_w, bag_y + SIZE * 0.08],
        start=180, end=360, fill=accent, width=int(SIZE * 0.025),
    )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    img.save(OUT_PATH)
    print("Salvato in", OUT_PATH)


if __name__ == "__main__":
    make_logo()
