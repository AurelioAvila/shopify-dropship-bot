"""
Genera un logo curato per lo store "Groomlyco & Magdock": icona che fonde
una zampa (Groomlyco/pet) con un anello magnetico (Magdock/tech), su
sfondo sfumato che unisce i due colori brand. Disegnato a 4x risoluzione
e ridotto con LANCZOS per bordi perfettamente lisci (supersampling).

Uso: python scripts/generate_store_logo.py
"""
import math
import os

from PIL import Image, ImageDraw

FINAL_SIZE = 512
SS = 4  # fattore di supersampling
SIZE = FINAL_SIZE * SS
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "branding", "store_logo.png")

SAGE_GREEN = (107, 143, 113)   # Groomlyco
ELECTRIC_BLUE = (64, 130, 220)  # Magdock


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _make_gradient_bg(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        t = y / size
        r = _lerp(SAGE_GREEN[0], ELECTRIC_BLUE[0], t)
        g = _lerp(SAGE_GREEN[1], ELECTRIC_BLUE[1], t)
        b = _lerp(SAGE_GREEN[2], ELECTRIC_BLUE[2], t)
        for x in range(size):
            px[x, y] = (r, g, b)
    return img


def make_logo() -> None:
    bg = _make_gradient_bg(SIZE)

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = int(SIZE * 0.04)
    mask_draw.rounded_rectangle([margin, margin, SIZE - margin, SIZE - margin], radius=int(SIZE * 0.22), fill=255)

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.paste(bg, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    cx, cy = SIZE / 2, SIZE / 2

    # Anello magnetico (Magdock) - cerchio spesso con un piccolo "dente" di
    # aggancio, dietro/attorno alla zampa
    ring_r = SIZE * 0.30
    ring_w = int(SIZE * 0.045)
    draw.ellipse(
        [cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
        outline=(255, 255, 255, 235), width=ring_w,
    )
    # piccolo tick di aggancio in alto sull'anello, come un connettore
    tick_r = SIZE * 0.025
    tick_x, tick_y = cx, cy - ring_r
    draw.ellipse([tick_x - tick_r, tick_y - tick_r, tick_x + tick_r, tick_y + tick_r], fill=(255, 255, 255, 255))

    # Zampa (Groomlyco) centrata dentro l'anello
    pad_w, pad_h = SIZE * 0.20, SIZE * 0.145
    draw.ellipse(
        [cx - pad_w / 2, cy - pad_h / 2 + SIZE * 0.02, cx + pad_w / 2, cy + pad_h / 2 + SIZE * 0.02],
        fill=(255, 255, 255, 255),
    )
    toe_r = SIZE * 0.052
    for angle_deg, dist in [(-58, 0.155), (-20, 0.175), (20, 0.175), (58, 0.155)]:
        angle = math.radians(angle_deg - 90)
        tx = cx + math.cos(angle) * SIZE * dist
        ty = cy + math.sin(angle) * SIZE * dist - SIZE * 0.075
        draw.ellipse([tx - toe_r, ty - toe_r, tx + toe_r, ty + toe_r], fill=(255, 255, 255, 255))

    final = img.resize((FINAL_SIZE, FINAL_SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    final.save(OUT_PATH)
    print("Salvato in", OUT_PATH)


if __name__ == "__main__":
    make_logo()
