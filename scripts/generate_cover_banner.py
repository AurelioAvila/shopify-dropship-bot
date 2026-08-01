"""
Genera l'immagine di copertina (1920x1080) per lo store "Groomlyco &
Magdock" - stesso stile del logo (gradiente verde->blu, monogramma GM)
ma pensata per il formato largo, non solo il logo ridimensionato.

Uso: python scripts/generate_cover_banner.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

FINAL_W, FINAL_H = 1920, 1080
SS = 2
W, H = FINAL_W * SS, FINAL_H * SS
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "branding", "store_cover.png")
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Poppins-ExtraBold.ttf")

SAGE_GREEN = (107, 143, 113)
ELECTRIC_BLUE = (64, 130, 220)
ACCENT = (255, 255, 255)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _make_gradient(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w) * 0.6 + (y / h) * 0.4  # diagonale, leggermente piu' orizzontale
            px[x, y] = (
                _lerp(SAGE_GREEN[0], ELECTRIC_BLUE[0], t),
                _lerp(SAGE_GREEN[1], ELECTRIC_BLUE[1], t),
                _lerp(SAGE_GREEN[2], ELECTRIC_BLUE[2], t),
            )
    return img


def make_cover() -> None:
    img = _make_gradient(W, H).convert("RGBA")
    draw = ImageDraw.Draw(img)

    font_big = ImageFont.truetype(FONT_PATH, int(H * 0.30))
    font_small = ImageFont.truetype(FONT_PATH, int(H * 0.055))

    def _draw_centered(text: str, x: float, y: float, color, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x - w / 2 - bbox[0], y - h / 2 - bbox[1]), text, font=font, fill=color)

    cx, cy = W / 2, H * 0.42
    offset = W * 0.045
    _draw_centered("G", cx - offset, cy, ACCENT, font_big)
    _draw_centered("M", cx + offset, cy, ACCENT, font_big)

    _draw_centered("GROOMLYCO  &  MAGDOCK", W / 2, H * 0.72, (255, 255, 255, 235), font_small)

    final = img.resize((FINAL_W, FINAL_H), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    final.save(OUT_PATH)
    print("Salvato in", OUT_PATH)


if __name__ == "__main__":
    make_cover()
