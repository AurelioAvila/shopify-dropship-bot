"""
Genera la miniatura per i video LONG-FORM (buying guide) e la carica su
YouTube.

PERCHE' ESISTE (2026-08-02): i buying guide sono la leva RPM del progetto
(video lunghi, non Shorts) ma non impostavano nessuna miniatura, quindi
YouTube ne sceglieva una da un fotogramma a caso - tipicamente meta' di una
parola dei sottotitoli sopra una foto prodotto, senza alcun rapporto col
titolo. Sugli Shorts la miniatura conta poco (il feed parte in autoplay), su
un video lungo e' LA leva del click. Stessa diagnosi gia' fatta e risolta
sui long-form di SoloFounded (vedi src/thumbnail.py in quel repo).

NOTA: le miniature personalizzate richiedono un canale con numero di telefono
verificato. Se l'API le rifiuta il video resta comunque pubblicato con quella
automatica - upload_thumbnail non solleva mai.
"""
import os
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 1280, 720
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Poppins-ExtraBold.ttf")

# Un colore d'accento per brand: i video dello stesso brand si riconoscono a
# colpo d'occhio nella griglia del canale senza dover leggere il titolo.
BRAND_COLORS = {
    "GROOMLYCO": (255, 149, 64),   # arancio caldo, coerente col mondo pet
    "MAGDOCK": (0, 176, 255),      # azzurro tech
}
DEFAULT_COLOR = (255, 193, 7)


def _extract_frame(video_path: str, out_path: str, at_seconds: float = 3.0) -> bool:
    """Estrae un fotogramma da usare come sfondo. Se ffmpeg manca o fallisce
    si usa una tinta piena: meglio una miniatura semplice ma leggibile che
    nessuna miniatura."""
    import subprocess

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", video_path,
             "-frames:v", "1", "-q:v", "2", out_path],
            check=True, capture_output=True, timeout=60,
        )
        return os.path.exists(out_path)
    except Exception:
        return False


def _background(video_path: str, color: tuple, tmp_dir: str) -> Image.Image:
    frame_path = os.path.join(tmp_dir, "_thumb_frame.jpg")
    if video_path and _extract_frame(video_path, frame_path):
        img = Image.open(frame_path).convert("RGB").resize((WIDTH, HEIGHT))
        # Sfocatura + scurimento: il fotogramma resta come contesto visivo ma
        # non compete col testo. Senza, il bianco diventa illeggibile sulle
        # zone chiare - ed e' esattamente cio' che rende inutili le miniature
        # automatiche di YouTube.
        img = img.filter(ImageFilter.GaussianBlur(6))
        img = Image.blend(img, Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0)), 0.55)
    else:
        img = Image.new("RGB", (WIDTH, HEIGHT), (18, 18, 26))
        draw = ImageDraw.Draw(img)
        for y in range(HEIGHT):
            t = y / HEIGHT
            draw.line([(0, y), (WIDTH, y)], fill=(
                int(18 + color[0] * 0.10 * t),
                int(18 + color[1] * 0.10 * t),
                int(26 + color[2] * 0.10 * t),
            ))
    return img


def _fit_font(text: str, max_width: int, max_height: int, max_lines: int):
    """Sceglie il corpo piu' grande che sta nello spazio disponibile: su una
    miniatura il testo dev'essere leggibile anche nell'anteprima piccola del
    feed mobile, dove si vede prima del titolo."""
    for size in range(96, 40, -4):
        try:
            font = ImageFont.truetype(FONT_PATH, size)
        except Exception:
            return ImageFont.load_default(), [text]

        chars_per_line = max(12, int(max_width / (size * 0.55)))
        lines = textwrap.wrap(text, width=chars_per_line)
        if len(lines) > max_lines:
            continue
        widest = max((font.getbbox(l)[2] - font.getbbox(l)[0]) for l in lines)
        if widest <= max_width and len(lines) * (size + 12) <= max_height:
            return font, lines

    fallback = ImageFont.truetype(FONT_PATH, 44) if os.path.exists(FONT_PATH) else ImageFont.load_default()
    return fallback, textwrap.wrap(text, width=26)[:max_lines]


def build_thumbnail(title: str, output_path: str, video_path: str = None, brand: str = None) -> str:
    """Miniatura 1280x720 col TITOLO in grande, non un frammento casuale."""
    color = BRAND_COLORS.get(brand, DEFAULT_COLOR)
    tmp_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    img = _background(video_path, color, tmp_dir)
    draw = ImageDraw.Draw(img)

    clean = " ".join(w for w in title.split() if not w.startswith("#")).strip()
    margin = 70
    font, lines = _fit_font(clean.upper(), WIDTH - margin * 2, HEIGHT - margin * 2 - 60, max_lines=4)

    line_h = (font.size + 14) if hasattr(font, "size") else 60
    y = (HEIGHT - len(lines) * line_h) // 2 - 10
    for line in lines:
        w = draw.textbbox((0, 0), line, font=font)[2]
        # Contorno nero spesso: leggibilita' garantita su qualunque sfondo.
        draw.text(((WIDTH - w) // 2, y), line, font=font, fill="white",
                  stroke_width=6, stroke_fill=(0, 0, 0))
        y += line_h

    draw.rectangle([(0, HEIGHT - 16), (WIDTH, HEIGHT)], fill=color)
    img.save(output_path, "JPEG", quality=92)
    return output_path


def upload_thumbnail(youtube, video_id: str, thumbnail_path: str) -> bool:
    """Non solleva mai: se il canale non ha il telefono verificato l'API
    rifiuta le miniature personalizzate, e in quel caso e' molto meglio
    tenere il video pubblicato con quella automatica che far fallire la
    pipeline dopo aver gia' renderizzato e caricato."""
    from googleapiclient.http import MediaFileUpload

    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        print(f"[thumbnail] miniatura personalizzata impostata su {video_id}", flush=True)
        return True
    except Exception as exc:
        print(f"[thumbnail] miniatura non impostata ({exc}) - resta quella automatica", flush=True)
        return False
