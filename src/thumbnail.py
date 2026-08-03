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


def _background(video_path: str, color: tuple, tmp_dir: str, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """width/height parametrizzati (2026-08-03): serve sia per la miniatura
    API 1280x720 sia per la card 1080x1920 bruciata nel video - vedi
    bake_thumbnail_card. Riempie e ritaglia al centro (cover-crop) invece di
    stirare, cosi' un fotogramma orizzontale usato come sfondo di una card
    verticale non risulta schiacciato."""
    frame_path = os.path.join(tmp_dir, "_thumb_frame.jpg")
    if video_path and _extract_frame(video_path, frame_path):
        src = Image.open(frame_path).convert("RGB")
        target_ratio = width / height
        if src.width / src.height > target_ratio:
            new_h = height
            new_w = int(src.width * (height / src.height))
        else:
            new_w = width
            new_h = int(src.height * (width / src.width))
        src = src.resize((new_w, new_h))
        left, top = (new_w - width) // 2, (new_h - height) // 2
        img = src.crop((left, top, left + width, top + height))
        # Sfocatura + scurimento: il fotogramma resta come contesto visivo ma
        # non compete col testo. Senza, il bianco diventa illeggibile sulle
        # zone chiare - ed e' esattamente cio' che rende inutili le miniature
        # automatiche di YouTube.
        img = img.filter(ImageFilter.GaussianBlur(6))
        img = Image.blend(img, Image.new("RGB", (width, height), (0, 0, 0)), 0.55)
    else:
        img = Image.new("RGB", (width, height), (18, 18, 26))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / height
            draw.line([(0, y), (width, y)], fill=(
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


def _render_card(title: str, output_path: str, video_path: str, brand: str, width: int, height: int) -> str:
    """Disegna il titolo in grande su uno sfondo sfocato, a qualunque
    dimensione richiesta. Condivisa da build_thumbnail (1280x720, per l'API)
    e bake_thumbnail_card (dimensioni del video reale, per il bake-in)."""
    color = BRAND_COLORS.get(brand, DEFAULT_COLOR)
    tmp_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    img = _background(video_path, color, tmp_dir, width=width, height=height)
    draw = ImageDraw.Draw(img)

    clean = " ".join(w for w in title.split() if not w.startswith("#")).strip()
    margin = max(40, int(width * 0.055))
    font, lines = _fit_font(clean.upper(), width - margin * 2, height - margin * 2 - int(height * 0.08), max_lines=4)

    line_h = (font.size + 14) if hasattr(font, "size") else 60
    y = (height - len(lines) * line_h) // 2 - 10
    for line in lines:
        w = draw.textbbox((0, 0), line, font=font)[2]
        # Contorno nero spesso: leggibilita' garantita su qualunque sfondo.
        draw.text(((width - w) // 2, y), line, font=font, fill="white",
                  stroke_width=6, stroke_fill=(0, 0, 0))
        y += line_h

    bar_h = max(10, int(height * 0.012))
    draw.rectangle([(0, height - bar_h), (width, height)], fill=color)
    img.save(output_path, "JPEG", quality=92)
    return output_path


def build_thumbnail(title: str, output_path: str, video_path: str = None, brand: str = None) -> str:
    """Miniatura 1280x720 col TITOLO in grande, non un frammento casuale.
    Formato fisso: e' quello richiesto dall'API di upload per l'immagine
    copertina, indipendentemente dall'orientamento del video."""
    return _render_card(title, output_path, video_path, brand, WIDTH, HEIGHT)


def _probe_dimensions(video_path: str):
    """Larghezza/altezza REALI del video, non assunte: i buying guide sono
    verticali (1080x1920), ma questo modulo deve restare corretto anche se un
    formato futuro fosse orizzontale. Ritorna None se ffprobe fallisce."""
    import subprocess

    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path],
            check=True, capture_output=True, timeout=30, text=True,
        ).stdout.strip()
        w, h = out.split(",")
        return int(w), int(h)
    except Exception:
        return None


def bake_thumbnail_card(video_path: str, title: str, brand: str = None, card_seconds: float = 4.0) -> bool:
    """Sovrappone una card col titolo in grande nei primi CARD_SECONDS
    secondi del video, IN PLACE - aggira il blocco delle miniature
    personalizzate su un canale senza telefono verificato.

    Perche' esiste (2026-08-03): confermato live che Groomlyco e Magdock
    hanno entrambi questo blocco (403 "insufficient permissions" su
    thumbnails.set), quindi upload_thumbnail sotto fallisce sempre. YouTube
    sceglie allora un fotogramma a caso del video come copertina - senza
    alcun rapporto col titolo. Bruciando il design nei primi secondi del
    video stesso, qualunque fotogramma YouTube scelga in quella finestra E'
    il design voluto, senza bisogno di nessun permesso.

    A DIFFERENZA di build_thumbnail (sempre 1280x720, il formato richiesto
    dall'API): qui la card viene generata alla RISOLUZIONE REALE del video
    (1080x1920 per i buying guide, verticali) - scalare un'immagine 16:9 su
    un frame 9:16 la distorcerebbe. La risoluzione si legge con ffprobe, non
    si assume.

    Non solleva mai: se qualunque passaggio fallisce il video resta quello
    originale, invariato - un video senza il fix e' molto meglio di nessun
    video.
    """
    import shutil
    import subprocess

    dims = _probe_dimensions(video_path)
    if not dims:
        print(f"[thumbnail] card saltata (risoluzione non rilevata): {os.path.basename(video_path)}", flush=True)
        return False
    w, h = dims

    tmp_dir = os.path.dirname(os.path.abspath(video_path)) or "."
    card_path = os.path.join(tmp_dir, "_thumb_card.jpg")
    tmp_video = video_path + ".card.mp4"

    try:
        _render_card(title, card_path, video_path, brand, w, h)

        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-i", card_path,
            "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='between(t,0,{card_seconds})'[v]",
            "-map", "[v]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "medium", "-b:v", "8000k",
            "-c:a", "copy",
            "-movflags", "+faststart",
            tmp_video,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=900)
        shutil.move(tmp_video, video_path)
        print(f"[thumbnail] card iniziale bruciata nei primi {card_seconds:.0f}s: {os.path.basename(video_path)}", flush=True)
        return True
    except Exception as exc:
        print(f"[thumbnail] card iniziale saltata ({exc}) - video invariato", flush=True)
        if os.path.exists(tmp_video):
            os.remove(tmp_video)
        return False
    finally:
        if os.path.exists(card_path):
            os.remove(card_path)


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
