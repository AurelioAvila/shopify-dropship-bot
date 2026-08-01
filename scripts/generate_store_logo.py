"""
Genera un logo per lo store "Groomlyco & Magdock": monogramma minimal
"G" + "M" su sfondo sfumato (verde Groomlyco -> blu Magdock), senza
elementi extra. Disegnato a 4x risoluzione e ridotto con LANCZOS per
bordi perfettamente lisci (supersampling).

Uso: python scripts/generate_store_logo.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

FINAL_SIZE = 512
SS = 4
SIZE = FINAL_SIZE * SS
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "branding", "store_logo.png")
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Poppins-ExtraBold.ttf")

SAGE_GREEN = (107, 143, 113)   # Groomlyco
ELECTRIC_BLUE = (64, 130, 220)  # Magdock
ACCENT = (255, 255, 255)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _make_gradient(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)  # diagonale, non solo verticale
            px[x, y] = (
                _lerp(SAGE_GREEN[0], ELECTRIC_BLUE[0], t),
                _lerp(SAGE_GREEN[1], ELECTRIC_BLUE[1], t),
                _lerp(SAGE_GREEN[2], ELECTRIC_BLUE[2], t),
            )
    return img


def make_logo() -> None:
    gradient = _make_gradient(SIZE)

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = int(SIZE * 0.04)
    mask_draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=int(SIZE * 0.24), fill=255)

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(FONT_PATH, int(SIZE * 0.34))

    def _draw_centered(text: str, x: float, y: float, color, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((x - w / 2 - bbox[0], y - h / 2 - bbox[1]), text, font=font, fill=color)

    cx, cy = SIZE / 2, SIZE / 2
    offset = SIZE * 0.135

    _draw_centered("G", cx - offset, cy, ACCENT, font)
    _draw_centered("M", cx + offset, cy, ACCENT, font)

    final = img.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    final.save(OUT_PATH)
    print("Salvato in", OUT_PATH)


if __name__ == "__main__":
    make_logo()
