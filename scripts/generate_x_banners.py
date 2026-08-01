"""Genera i banner X (Twitter) 1500x500 per Groomlyco e Magdock, stesso
stile geometrico e stessi colori dei profile logo (generate_logos.py) cosi'
i due brand restano coerenti tra le piattaforme.

Uso: python scripts/generate_x_banners.py
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1500, 500
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "branding")


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _font_regular(size: int) -> ImageFont.FreeTypeFont:
    for path in (
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_groomlyco_banner(path: str) -> None:
    bg = (107, 143, 113)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Zampette ripetute e sfumate sullo sfondo, a destra, come motivo
    # decorativo - non competono con testo/logo che restano a sinistra
    # (l'avatar del profilo si sovrappone in basso a sinistra su X).
    def paw(cx, cy, scale, alpha):
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        pad_w, pad_h = 90 * scale, 65 * scale
        ld.ellipse([cx - pad_w / 2, cy - pad_h / 2, cx + pad_w / 2, cy + pad_h / 2], fill=(255, 255, 255, alpha))
        toe_r = 22 * scale
        for angle_deg, dist in [(-55, 78), (-20, 88), (20, 88), (55, 78)]:
            angle = math.radians(angle_deg - 90)
            tx = cx + math.cos(angle) * dist * scale
            ty = cy + math.sin(angle) * dist * scale - 40 * scale
            ld.ellipse([tx - toe_r, ty - toe_r, tx + toe_r, ty + toe_r], fill=(255, 255, 255, alpha))
        img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))

    paw(1120, 150, 1.6, 40)
    paw(1300, 320, 1.1, 30)
    paw(1420, 110, 0.8, 25)

    font = _font(80)
    tagline_font = _font_regular(34)
    draw = ImageDraw.Draw(img)
    draw.text((70, 175), "Groomlyco", font=font, fill=(255, 255, 255))
    draw.text((74, 270), "Dog grooming, made simple", font=tagline_font, fill=(235, 240, 236))

    img.save(path)


def make_magdock_banner(path: str) -> None:
    bg = (18, 20, 28)
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    accent = (64, 156, 255)
    # Anelli concentrici ripetuti a destra (stesso motivo MagSafe del logo),
    # dimensione decrescente, look "tech" senza affollare il lato testo.
    rings = [(1180, 250, 150, 40, 255), (1330, 130, 90, 25, 180), (1420, 380, 70, 18, 140)]
    for cx, cy, r, width, alpha in rings:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*accent, alpha), width=width)
        img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"), (0, 0))

    dot_r = 16
    draw = ImageDraw.Draw(img)
    draw.ellipse([1180 - dot_r, 250 - dot_r, 1180 + dot_r, 250 + dot_r], fill=accent)

    font = _font(80)
    tagline_font = _font_regular(34)
    draw.text((70, 175), "Magdock", font=font, fill=(255, 255, 255))
    draw.text((74, 270), "MagSafe & car mounts that actually hold", font=tagline_font, fill=(220, 228, 240))

    img.save(path)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    make_groomlyco_banner(os.path.join(OUT_DIR, "groomlyco_banner.png"))
    make_magdock_banner(os.path.join(OUT_DIR, "magdock_banner.png"))
    print("Salvati in", OUT_DIR)
