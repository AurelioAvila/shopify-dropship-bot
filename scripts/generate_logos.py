"""
Genera due profile picture semplici (1080x1080, requisito Instagram) per i
brand Groomlyco e Magdock, con un monogramma pulito - non servono asset
esterni, solo forme geometriche via Pillow.

Uso: python scripts/generate_logos.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 1080
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "branding")


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _centered_text(draw: ImageDraw.ImageDraw, text: str, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]), text, font=font, fill=fill)


def make_groomlyco_logo(path: str) -> None:
    bg = (107, 143, 113)  # sage green - calmo, coerente col branding "pet care"
    img = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)

    # Zampetta stilizzata: 1 pad grande + 4 dita, sopra il monogramma
    cx, cy = SIZE * 0.5, SIZE * 0.38
    pad_w, pad_h = SIZE * 0.22, SIZE * 0.16
    draw.ellipse(
        [cx - pad_w / 2, cy - pad_h / 2, cx + pad_w / 2, cy + pad_h / 2],
        fill=(255, 255, 255),
    )
    toe_r = SIZE * 0.055
    for angle_deg, dist in [(-55, 0.19), (-20, 0.21), (20, 0.21), (55, 0.19)]:
        angle = math.radians(angle_deg - 90)
        tx = cx + math.cos(angle) * SIZE * dist
        ty = cy + math.sin(angle) * SIZE * dist - SIZE * 0.10
        draw.ellipse([tx - toe_r, ty - toe_r, tx + toe_r, ty + toe_r], fill=(255, 255, 255))

    font = _font(int(SIZE * 0.16))
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), "Groomlyco", font=font)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE - w) / 2 - bbox[0], SIZE * 0.66), "Groomlyco", font=font, fill=(255, 255, 255))

    img.save(path)


def make_magdock_logo(path: str) -> None:
    bg = (18, 20, 28)  # quasi nero, tech/minimal
    img = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)

    accent = (64, 156, 255)  # blu elettrico
    cx, cy, r = SIZE * 0.5, SIZE * 0.38, SIZE * 0.16
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=int(SIZE * 0.03))
    dot_r = SIZE * 0.035
    draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=accent)

    font = _font(int(SIZE * 0.17))
    bbox = draw.textbbox((0, 0), "Magdock", font=font)
    w = bbox[2] - bbox[0]
    draw.text(((SIZE - w) / 2 - bbox[0], SIZE * 0.64), "Magdock", font=font, fill=(255, 255, 255))

    img.save(path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    make_groomlyco_logo(os.path.join(OUT_DIR, "groomlyco_profile.png"))
    make_magdock_logo(os.path.join(OUT_DIR, "magdock_profile.png"))
    print("Salvate in", OUT_DIR)
