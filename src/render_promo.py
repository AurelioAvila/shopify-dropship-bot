"""
Monta un video promozionale verticale (1080x1920) a partire da:
- una lista di immagini prodotto (effetto Ken Burns: leggero zoom/pan)
- un copione, letto con voce IA (edge-tts) e sottotitolato in automatico
Stessa impostazione visiva (font, stroke, banda sottotitoli) del bot Shorts.
"""
import json
import os

# Windows ha un convert.exe di sistema (System32) che non c'entra con
# ImageMagick e confonde moviepy se non gli si punta esplicitamente al
# binario giusto - deve essere impostato PRIMA di importare moviepy.editor.
_IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"
if os.path.exists(_IMAGEMAGICK_BINARY):
    os.environ["IMAGEMAGICK_BINARY"] = _IMAGEMAGICK_BINARY

import PIL.Image

# Pillow >=10 ha rimosso Image.ANTIALIAS (deprecato in favore di Resampling.LANCZOS);
# moviepy 1.0.3 lo usa ancora internamente. Shim di compatibilita' invece di
# fissare una versione vecchia di Pillow (che qui non ha wheel precompilate).
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import subprocess

import requests
from PIL import ImageEnhance, ImageFilter
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from src.footage import download_background_video
from src.tts import generate_audio_with_timing

# Query Pexels per nicchia - usate per lo sfondo VIDEO reale dietro il
# prodotto (vedi _ken_burns_clip) invece della vecchia foto-prodotto
# sfocata come unico sfondo, che restava un blob piatto e "sbiadito" a
# prescindere da quanto si spingesse saturazione/contrasto (segnalazione
# utente 2026-08-01, verificata visivamente su foto prodotto reali con
# sfondo bianco da studio - non c'e' nessun dettaglio da recuperare
# sfocando quel tipo di foto). Stesso principio dei creator veri di
# product-ad: b-roll di lifestyle reale dietro, prodotto nitido sopra.
FOOTAGE_QUERIES = {
    "PET": ["dog playing home", "puppy owner lifestyle", "dog grooming", "pet care home"],
    "TECH": ["phone accessories desk", "smartphone lifestyle", "tech desk setup", "car dashboard phone"],
    # Beffante (2026-08-04): senza questa entry ricadrebbe su FOOTAGE_QUERIES
    # ["TECH"], tutto incentrato su telefono/auto - non coerente con
    # proiettori/webcam/videosorveglianza/casa intelligente.
    "HOME": ["home office setup", "video call laptop webcam", "smart home technology", "cozy living room evening"],
}


def _generate_bg_music(path: str, duration: float) -> None:
    """Sottofondo strumentale sintetizzato (accordo soffuso, nessun sample
    esterno - stesso approccio gia' usato per CertSprint, evita ogni rischio
    di copyright).

    LIVELLO CORRETTO 2026-08-04 (era volume=0.05, misurato INUDIBILE su
    youtube-shorts-bot/solofounded-bot con lo stesso identico valore copiato
    proprio da qui: -53 dB contro i -21.5 dB della voce TTS, cioe' 32 dB
    sotto - aggiungerlo cambiava il volume del mix di 0.0 dB. Musica che non
    si sente non e' musica. 0.18 porta il sottofondo a ~21 dB sotto la voce,
    dentro lo standard 15-25 dB per musica sotto narrazione.

    TREMOLO: un accordo di sinusoidi tenuto fisso e' un drone, e a volume
    finalmente udibile un drone fisso stanca piu' del silenzio - una
    modulazione lenta (0.25 Hz, un ciclo ogni 4s) lo fa "respirare".
    Questo bug/fix riguarda TUTTI E TRE i brand (Groomlyco/Magdock/Beffante):
    e' la stessa funzione condivisa, non serve differenziare per brand."""
    fade_in = min(duration * 0.4, 6.0)
    fade_out = min(duration * 0.15, 2.0)
    fade_out_start = max(duration - fade_out, 0.0)
    notes = [130.81, 164.81, 196.00]  # accordo di Do maggiore (C-E-G), soffuso
    cmd = ["ffmpeg", "-y"]
    for freq in notes:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={duration}"]
    cmd += [
        "-filter_complex",
        f"amix=inputs={len(notes)}:duration=longest,"
        f"volume=0.18,"
        f"tremolo=f=0.25:d=0.35,"
        f"afade=t=in:st=0:d={fade_in:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}",
        str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


# Test cross-promo (2026-08-02, richiesta utente): come gia' fatto per
# CertSprint, prova una traccia strumentale reale dell'artista "Low Static"
# (progetto musicale dello stesso utente, zero rischio di licenza) al posto
# dell'accordo sintetizzato, per un numero limitato di generazioni per brand
# prima di decidere se tenerla. Traccia diversa per brand cosi' il test copre
# anche varieta' di genere, non solo "musica reale si/no":
# - Groomlyco (pet, tono caldo/rassicurante) -> "Fading into the Static" (warm/analog)
# - Magdock (tech, tono moderno) -> "Beneath the Static" (dark ambient)
_MUSIC_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "music")
LOW_STATIC_TEST_TRACKS = {
    "PET": os.path.join(_MUSIC_DIR, "low_static_fading_into_the_static.mp3"),
    "TECH": os.path.join(_MUSIC_DIR, "low_static_beneath_the_static.mp3"),
}
LOW_STATIC_TEST_STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "low_static_test_state.json")
LOW_STATIC_TEST_VIDEO_LIMIT_PER_NICHE = 6  # ~1 settimana di run prima di rivalutare con l'utente


def _load_low_static_test_count(niche: str) -> int:
    if not os.path.exists(LOW_STATIC_TEST_STATE_PATH):
        return 0
    with open(LOW_STATIC_TEST_STATE_PATH) as f:
        return json.load(f).get(niche, 0)


def _bump_low_static_test_count(niche: str) -> None:
    os.makedirs(os.path.dirname(LOW_STATIC_TEST_STATE_PATH), exist_ok=True)
    counts = {}
    if os.path.exists(LOW_STATIC_TEST_STATE_PATH):
        with open(LOW_STATIC_TEST_STATE_PATH) as f:
            counts = json.load(f)
    counts[niche] = counts.get(niche, 0) + 1
    with open(LOW_STATIC_TEST_STATE_PATH, "w") as f:
        json.dump(counts, f)


def _generate_bg_music_from_track(path: str, duration: float, track_path: str) -> None:
    """Stesso trattamento (volume basso, fade in/out) ma partendo da una
    traccia reale invece dei toni sintetizzati - loopata e tagliata sulla
    durata esatta del video."""
    fade_in = min(duration * 0.4, 6.0)
    fade_out = min(duration * 0.15, 2.0)
    fade_out_start = max(duration - fade_out, 0.0)
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", track_path,
        "-t", f"{duration:.3f}",
        "-af",
        f"volume=0.12,"
        f"afade=t=in:st=0:d={fade_in:.3f},"
        f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}",
        str(path),
    ], check=True, capture_output=True)


def _make_bg_music(path: str, duration: float, niche: str = None) -> None:
    """Sceglie tra la traccia di test Low Static (per nicchia) e il
    sottofondo sintetizzato di default, fino a esaurimento del tetto di test."""
    track_path = LOW_STATIC_TEST_TRACKS.get(niche) if niche else None
    if track_path and os.path.exists(track_path) and _load_low_static_test_count(niche) < LOW_STATIC_TEST_VIDEO_LIMIT_PER_NICHE:
        _generate_bg_music_from_track(path, duration, track_path)
        _bump_low_static_test_count(niche)
    else:
        _generate_bg_music(path, duration)


def _generate_whoosh(path: str, duration: float = 0.3) -> None:
    """Whoosh sintetizzato (rumore filtrato con fade) per marcare i tagli tra
    un'immagine e l'altra. La banda larga precedente (800-6000Hz) a volume
    0.35 lasciava passare sia il "ronzio" grave che il sibilo acuto del
    rumore rosa grezzo, che senza uno sweep di frequenza (i whoosh veri usano
    un filtro che si sposta nel tempo, non una banda fissa) si sentiva come
    un fruscio/graffio violento invece che un passaggio morbido - segnalato
    dall'utente 2026-08-02 su Groomlyco. Banda piu' stretta e centrale,
    volume molto piu' basso, fade piu' lunghi e morbidi."""
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anoisesrc=color=pink:duration={duration}:sample_rate=44100",
        "-af", (
            "highpass=f=2500,lowpass=f=4500,"
            "afade=t=in:st=0:d=0.1,"
            f"afade=t=out:st={duration - 0.12:.3f}:d=0.12,"
            "volume=0.12"
        ),
        str(path),
    ], check=True, capture_output=True)


TARGET_W, TARGET_H = 1080, 1920

# Normalizzazione loudness a -14 LUFS, lo standard di fatto per streaming e
# social (2026-08-02). Il bitrate qui era gia' esplicito (fix anti-sfocato),
# ma l'audio no: misurato -23.9 dB medi su un promo reale, quasi 10 dB sotto
# lo standard. Nel feed un video piu' basso degli altri suona "debole" e
# invita allo scroll - nessuno alza il volume, si passa al video dopo.
LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11"


def _normalize_loudness(path: str) -> None:
    """Porta l'audio del video gia' renderizzato a -14 LUFS.

    NON si puo' fare con ffmpeg_params=["-af", ...] in write_videofile:
    moviepy muxa l'audio in "codec copy" e ffmpeg rifiuta filtro + streamcopy
    insieme ("Filtering and streamcopy cannot be used together") - verificato
    con smoke test, il render fallisce del tutto.

    Il video e' copiato bit-per-bit (-c:v copy): nessuna ricompressione
    video. Se ffmpeg fallisce il file originale resta intatto - un audio non
    normalizzato e' molto meglio di nessun video.
    """
    import shutil

    tmp_path = path + ".norm.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", path,
        "-c:v", "copy",
        "-af", LOUDNORM_FILTER,
        "-c:a", "aac", "-b:a", "192k",
        # Questa passata rimuxa: senza ri-specificare +faststart il moov atom
        # tornerebbe in fondo, riportando il bug del "primo tap non parte".
        "-movflags", "+faststart",
        tmp_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.move(tmp_path, path)
        print(f"  [render] audio normalizzato a -14 LUFS: {os.path.basename(path)}")
    except Exception as exc:
        print(f"  [render] normalizzazione audio saltata ({exc}) - video invariato")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


CAPTION_CHUNK_SIZE = 2
CAPTION_FONTSIZE = 80
CAPTION_Y = int(TARGET_H * 0.62)
CAPTION_BAND_Y = int(TARGET_H * 0.56)
CAPTION_BAND_HEIGHT = int(TARGET_H * 0.22)
CAPTION_POP_SECONDS = 0.12

# HOOK CARD (aggiunto 2026-08-02) - la singola leva piu' importante trovata
# nell'audit sulle view basse. Le didascalie sono sincronizzate a 2 parole
# per volta, quindi al fotogramma 0 lo spettatore leggeva solo un frammento
# senza senso ("If your", "This is") proprio nei 3 secondi in cui decide se
# restare o scrollare. La ricerca 2026 (Hansen Insights, Aibrify, HypeNest)
# e' netta: sotto l'80% di retention nei primi 3 secondi il video muore nel
# cold start senza mai essere distribuito. Ora la promessa COMPLETA e'
# leggibile istantaneamente dal primo fotogramma, sopra le didascalie.
HOOK_CARD_SECONDS = 2.8
HOOK_CARD_FONTSIZE = 66
HOOK_CARD_Y = int(TARGET_H * 0.20)

# Same bundled font as the other video pipelines (PC Tweaker, Shorts bot) -
# ImageMagick's Windows build silently falls back to a thin default font
# (no error) when given a font path with backslashes, so always normalize
# to forward slashes.
FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "Poppins-ExtraBold.ttf").replace(os.sep, "/")


# Sotto questa risoluzione (lato corto, px) un'immagine prodotto CJ e' quasi
# certamente troppo piccola per riempire un frame 1080x1920 senza sfocarsi
# visibilmente - non blocchiamo il render (meglio sfocato che niente), ma
# segnaliamo cosi' si puo' andare a cercare un'immagine migliore su CJ.
MIN_SAFE_SHORT_SIDE = 900

# Sopra questo fattore di ingrandimento "obbligato" (solo per riempire il
# frame, PRIMA di ogni zoom Ken Burns) la sfocatura diventa evidente - da
# quel punto in poi riduciamo drasticamente lo zoom aggiuntivo invece di
# sommarci sopra altro ingrandimento.
SAFE_UPSCALE_FACTOR = 1.3


class LowResolutionError(Exception):
    """Nessuna immagine del prodotto e' abbastanza nitida da garantire lo
    stesso standard qualitativo delle altre pipeline (CertSprint/PC Tweaker
    usano footage stock sempre ad alta risoluzione, quindi non hanno questo
    problema) - il chiamante deve saltare il prodotto invece di pubblicare
    un video visibilmente sfocato."""


def download_images(urls: list[str], tmp_dir: str, enforce_min_resolution: bool = True) -> list[tuple[str, int, int]]:
    """Scarica le immagini e ritorna (path, width, height) di ciascuna, ordinate
    per risoluzione decrescente - cosi' le immagini piu' nitide vengono usate
    per prime/piu' spesso quando servono piu' segmenti delle immagini disponibili.

    Filtro rigido (non solo un warning): se anche la migliore immagine
    disponibile e' sotto MIN_SAFE_SHORT_SIDE, solleva LowResolutionError
    invece di procedere - meglio saltare il prodotto che pubblicare un
    Reel sotto lo standard qualitativo degli altri account.

    enforce_min_resolution=False quando build_promo_video ha gia' uno sfondo
    VIDEO reale di nicchia disponibile (vedi fetch_niche_background_clips) -
    in quel caso il prodotto in primo piano non viene MAI ingrandito oltre
    la sua risoluzione nativa (fit_scale capped a 1.0 in _ken_burns_clip),
    quindi il rischio di sfocatura che questo filtro esisteva per evitare
    (il vecchio sfondo-sfocato-della-stessa-foto, ingrandito 3x+) non si
    applica piu' - tenere il filtro attivo in quel caso scartava inutilmente
    prodotti validi solo perche' le loro foto erano poco sopra/sotto gli 800px
    (segnalazione utente 2026-08-01, verificato live su Groomlyco: molti
    prodotti CJ hanno foto esattamente 800x800, appena sotto la vecchia
    soglia di 900)."""
    os.makedirs(tmp_dir, exist_ok=True)
    results = []
    for i, url in enumerate(urls):
        path = os.path.join(tmp_dir, f"img_{i}.jpg")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        with PIL.Image.open(path) as im:
            w, h = im.size
        results.append((path, w, h))

    results.sort(key=lambda r: r[1] * r[2], reverse=True)

    best_short_side = min(results[0][1], results[0][2]) if results else 0
    if enforce_min_resolution and best_short_side < MIN_SAFE_SHORT_SIDE:
        raise LowResolutionError(
            f"anche la migliore immagine disponibile e' solo "
            f"{results[0][1]}x{results[0][2]}px - sotto la soglia di "
            f"{MIN_SAFE_SHORT_SIDE}px, il video uscirebbe visibilmente sfocato."
        )
    return results


def _make_blurred_background(image_path: str, tmp_dir: str) -> str:
    """Cover-crops + heavily blurs the product photo to fill the frame as a
    backdrop. Confirmed live (2026-07-30) that real CJ product photos come
    back as small as 600x600 - a plain cover-crop into 1080x1920 forces a
    3.2x+ upscale before any Ken Burns zoom even runs, which is visibly
    blurry regardless of video bitrate (that's a source-resolution problem,
    not an encoding one - capping the zoom alone doesn't fix it). Real
    product-ad creators solve exactly this with a blurred full-bleed
    backdrop (intentional softness) behind a sharp, never-overscaled
    product cutout - see _ken_burns_clip, which layers this behind that."""
    img = PIL.Image.open(image_path).convert("RGB")
    if img.width / img.height > TARGET_W / TARGET_H:
        new_h, new_w = TARGET_H, int(img.width * (TARGET_H / img.height))
    else:
        new_w, new_h = TARGET_W, int(img.height * (TARGET_W / img.width))
    img = img.resize((new_w, new_h), PIL.Image.LANCZOS)
    left, top = (new_w - TARGET_W) // 2, (new_h - TARGET_H) // 2
    img = img.crop((left, top, left + TARGET_W, top + TARGET_H))
    img = img.filter(ImageFilter.GaussianBlur(radius=40))

    # Corretto 2026-08-01 (segnalazione utente: "sbiadito" su Magdock, non
    # sulla concorrenza es. CertSprint). Causa reale, verificata visivamente
    # frame per frame: una sfocatura pesante su una foto con piu' colori
    # (es. una tabella campioni colore) media tutto verso un grigio
    # uniforme - il vecchio oscuramento lineare (moltiplicare ogni canale
    # per 0.55) accentuava ulteriormente quell'effetto "grigiore", mentre
    # CertSprint usa filmati stock gia' saturi e non ha questo problema.
    # Fix: ripristinare la saturazione DOPO la sfocatura (che la sfocatura
    # stessa attenua) prima di scurire, cosi' lo sfondo resta scuro ma
    # colorato invece che grigio spento.
    img = ImageEnhance.Color(img).enhance(1.6)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = PIL.Image.eval(img, lambda p: int(p * 0.55))  # darken so white captions stay readable

    out_path = os.path.join(tmp_dir, f"bg_{os.path.basename(image_path)}")
    img.save(out_path, quality=85)
    return out_path


def _fit_vertical(clip: VideoFileClip) -> VideoFileClip:
    target_ratio = TARGET_W / TARGET_H
    if clip.w / clip.h > target_ratio:
        clip = clip.resize(height=TARGET_H)
    else:
        clip = clip.resize(width=TARGET_W)
    return clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=TARGET_W, height=TARGET_H)


def _loop_to_duration(clip: VideoFileClip, duration: float) -> VideoFileClip:
    if clip.duration >= duration:
        return clip.subclip(0, duration)
    n_loops = int(duration // clip.duration) + 1
    return concatenate_videoclips([clip] * n_loops).subclip(0, duration)


def fetch_niche_background_clips(niche: str, count: int, tmp_dir: str) -> list:
    """Scarica 'count' clip Pexels vere per la nicchia (PET/TECH), cicliche
    tra le query disponibili - stesso pattern multi-clip gia' usato in
    CertSprint/PC Tweaker. Ritorna [] (non solleva) se Pexels fallisce, cosi'
    il chiamante puo' ricadere sul vecchio sfondo sfumato invece di bloccare
    l'intera pubblicazione per un problema di rete/quota su una risorsa
    puramente estetica."""
    pool = FOOTAGE_QUERIES.get(niche, FOOTAGE_QUERIES["TECH"])
    paths = []
    for i in range(count):
        query = pool[i % len(pool)]
        path = os.path.join(tmp_dir, f"bgvideo_{i}.mp4")
        try:
            download_background_video(path, query=query)
            paths.append(path)
        except Exception as exc:
            print(f"  [WARN] sfondo video Pexels non disponibile ('{query}': {exc}), uso il fallback sfumato per questo segmento")
    return paths


def _ken_burns_clip(image_path: str, img_w: int, img_h: int, duration: float, tmp_dir: str, zoom_in: bool = True, bg_video_path: str = None) -> ImageClip:
    if bg_video_path:
        background = _loop_to_duration(_fit_vertical(VideoFileClip(bg_video_path)), duration)
    else:
        bg_path = _make_blurred_background(image_path, tmp_dir)
        background = ImageClip(bg_path).set_duration(duration)

    # Sharp foreground: fit-to-frame WITHOUT upscaling past native
    # resolution (capped at 1.0), unlike the old cover-crop that forced a
    # 3.2x+ upscale on small source photos - a 600x600 product shows at
    # true native size (letterboxed, backed by the blurred full-bleed
    # layer) instead of being stretched into visible mush.
    fit_scale = min(TARGET_W / img_w, TARGET_H / img_h, 1.0)
    product = ImageClip(image_path).resize(fit_scale)

    # Ken Burns zoom on top of fit_scale, capped so the TOTAL scale (fit *
    # zoom) never crosses SAFE_UPSCALE_FACTOR past native resolution -
    # small images get a near-static frame (little zoom headroom left),
    # already-large images still get a normal Ken Burns pan/zoom.
    max_total_scale = min(SAFE_UPSCALE_FACTOR / max(fit_scale, 0.01), 1.15)
    start_scale, end_scale = (1.0, max_total_scale) if zoom_in else (max_total_scale, 1.0)

    def scale_at(t):
        progress = t / duration
        return start_scale + (end_scale - start_scale) * progress

    zoomed_product = product.resize(lambda t: scale_at(t)).set_position(("center", "center"))
    return CompositeVideoClip([background, zoomed_product], size=(TARGET_W, TARGET_H)).set_duration(duration)


def _make_caption_clip(text: str, start: float, duration: float):
    duration = max(duration, 0.1)
    pop = min(CAPTION_POP_SECONDS, duration / 2)

    def _pop_scale(t, pop=pop):
        return 1.0 if t >= pop else 0.85 + 0.15 * (t / pop)

    # ImageMagick's combined -fill + -stroke on a single "caption:" (Pango)
    # pass is unreliable on this machine's IM build - confirmed live
    # (2026-07-30) it intermittently renders outline-only with ZERO fill,
    # reproducible even in total isolation with no code change between
    # runs (same exact command, same text, flaky pass-to-pass). Splitting
    # into two separate TextClips - a solid stroke-color block underneath,
    # a plain white fill with no stroke on top - avoids the buggy combined
    # code path entirely and has been reliable across repeated tests.
    common = dict(fontsize=CAPTION_FONTSIZE, method="caption", size=(TARGET_W - 100, None), font=FONT_PATH)
    stroke_layer = TextClip(text, color="black", stroke_color="black", stroke_width=6, **common)
    fill_layer = TextClip(text, color="white", **common)

    clip = (
        CompositeVideoClip([stroke_layer, fill_layer.set_position(("center", "center"))], size=stroke_layer.size)
        .set_start(start)
        .set_duration(duration)
        .resize(_pop_scale)
        .set_position(("center", CAPTION_Y))
    )
    return clip


def _make_hook_card(hook_text: str, duration: float):
    """Full hook sentence, readable at frame 0, over its own dark backdrop.

    Deliberately NO pop/scale animation and no fade-in: the whole point is
    that it's already fully legible in the very first frame, before the
    viewer's thumb decides. Any entrance animation costs exactly the
    milliseconds that matter most."""
    text = hook_text.strip()
    if not text:
        return []

    common = dict(
        fontsize=HOOK_CARD_FONTSIZE, method="caption",
        size=(TARGET_W - 140, None), font=FONT_PATH, align="center",
    )
    # Stessa tecnica a due livelli delle didascalie: la combinazione
    # fill+stroke in un unico passaggio ImageMagick e' inaffidabile su questa
    # macchina (vedi il commento in _make_caption_clip).
    stroke_layer = TextClip(text, color="black", stroke_color="black", stroke_width=7, **common)
    fill_layer = TextClip(text, color="white", **common)

    card_w, card_h = stroke_layer.size
    # 0.78 e non ~0.6: su sfondi chiari un nero al 60% legge come un riquadro
    # grigio slavato (verificato sul primo render di prova), che fa sembrare
    # il video amatoriale invece di un elemento grafico voluto.
    backdrop = (
        ColorClip(size=(card_w + 60, card_h + 50), color=(0, 0, 0))
        .set_opacity(0.78)
        .set_duration(duration)
    )
    text_group = CompositeVideoClip(
        [stroke_layer, fill_layer.set_position(("center", "center"))],
        size=(card_w, card_h),
    ).set_duration(duration)

    card = CompositeVideoClip(
        [backdrop, text_group.set_position(("center", "center"))],
        size=(card_w + 60, card_h + 50),
    ).set_duration(duration).set_start(0).set_position(("center", HOOK_CARD_Y))
    return [card]


def _caption_clips_timed(word_timings: list, skip_before: float = 0.0):
    """skip_before: quando c'e' l'hook card, le didascalie parola-per-parola
    dei primi secondi ripetono esattamente il testo gia' mostrato per intero
    dalla card - due riquadri sovrapposti che dicono la stessa cosa. Si
    saltano, cosi' l'apertura resta pulita e la card e' l'unico elemento
    che l'occhio deve leggere."""
    if not word_timings:
        return []
    chunks, current = [], []
    for w in word_timings:
        current.append(w)
        ends_sentence = w["text"].rstrip().endswith((".", "!", "?"))
        if len(current) >= CAPTION_CHUNK_SIZE or ends_sentence:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    clips = []
    for chunk in chunks:
        text = " ".join(w["text"] for w in chunk)
        start = chunk[0]["offset"]
        end = chunk[-1]["offset"] + chunk[-1]["duration"]
        if start < skip_before:
            continue
        clips.append(_make_caption_clip(text, start, end - start))
    return clips


# Durata massima per singola immagine prima del prossimo taglio - stile
# retention-optimized Shorts (tagli rapidi), non slideshow lento.
MAX_SEGMENT_SECONDS = 2.5


def build_promo_video(script_text: str, image_urls: list[str], output_path: str, tmp_dir: str, niche: str = None, hook: str = None) -> str:
    audio_path = output_path.replace(".mp4", ".mp3")
    word_timings = generate_audio_with_timing(script_text, audio_path)
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    local_images = download_images(image_urls, tmp_dir, enforce_min_resolution=(niche is None))
    # Numero di segmenti = quanti tagli servono per stare sotto MAX_SEGMENT_SECONDS,
    # ma mai piu' immagini distinte di quelle disponibili moltiplicate per 2
    # (oltre le quali ricicleremmo troppo la stessa foto, diventa ripetitivo).
    import math
    target_segments = max(len(local_images), math.ceil(duration / MAX_SEGMENT_SECONDS))
    target_segments = min(target_segments, len(local_images) * 2)
    per_image = duration / target_segments

    # Sfondi VIDEO reali (b-roll di nicchia) invece della foto prodotto
    # sfocata - vedi FOOTAGE_QUERIES/fetch_niche_background_clips. Se Pexels
    # non e' disponibile per qualche motivo, bg_clips resta vuota e
    # _ken_burns_clip ricade da solo sul vecchio sfondo sfumato.
    bg_clips = fetch_niche_background_clips(niche, target_segments, tmp_dir) if niche else []

    image_clips = []
    for i in range(target_segments):
        # local_images e' gia' ordinata per risoluzione decrescente
        # (download_images): quando servono piu' segmenti delle immagini
        # disponibili, si ricicla ripartendo dalle piu' nitide.
        path, img_w, img_h = local_images[i % len(local_images)]
        bg_video_path = bg_clips[i % len(bg_clips)] if bg_clips else None
        # alterna zoom-in/zoom-out ogni volta, cosi' anche quando la stessa
        # immagine si ripete il movimento e' diverso e non sembra uno stallo
        image_clips.append(_ken_burns_clip(path, img_w, img_h, per_image, tmp_dir, zoom_in=(i % 2 == 0), bg_video_path=bg_video_path))
    background = concatenate_videoclips(image_clips).set_duration(duration)

    # Product photos on CJ are almost always plain white-background cutouts
    # (confirmed live 2026-07-30) - white caption text with only a black
    # stroke silently loses its fill's contrast whenever it lands over that
    # white area (the fill blends in, only the outline stays visible). A
    # semi-transparent dark band behind the captions guarantees contrast
    # regardless of what's behind them, same fix already used in the
    # sibling video pipelines (PC Tweaker, Shorts bot).
    # L'hook card non deve mai superare la durata del video (video molto
    # corti) ne' restare in scena dopo che la voce ha gia' superato l'hook.
    hook_seconds = min(HOOK_CARD_SECONDS, duration) if hook else 0.0
    hook_clips = _make_hook_card(hook, hook_seconds) if hook else []

    # La banda parte solo quando finisce l'hook card: durante l'apertura
    # l'unico elemento grafico deve essere la card, altrimenti si vedono due
    # riquadri scuri sovrapposti (verificato sul primo render di prova).
    band = (
        ColorClip(size=(TARGET_W, CAPTION_BAND_HEIGHT), color=(0, 0, 0))
        .set_opacity(0.45)
        .set_start(hook_seconds)
        .set_duration(max(duration - hook_seconds, 0.1))
        .set_position(("center", CAPTION_BAND_Y))
    )
    captions = _caption_clips_timed(word_timings, skip_before=hook_seconds)

    bg_music_path = output_path.replace(".mp4", "_bgmusic.mp3")
    _make_bg_music(bg_music_path, duration, niche=niche)
    bg_music = AudioFileClip(bg_music_path)

    # Whoosh discreto a ogni cambio immagine (tranne il primo, l'apertura non
    # ha bisogno di un "taglio" da segnare) - marca il ritmo dei tagli senza
    # mai coprire la voce (volume basso, dura solo 0.35s).
    whoosh_path = output_path.replace(".mp4", "_whoosh.wav")
    _generate_whoosh(whoosh_path)
    whoosh_layers = [
        AudioFileClip(whoosh_path).set_start(i * per_image)
        for i in range(1, target_segments)
    ]

    full_audio = CompositeAudioClip([bg_music, audio, *whoosh_layers])

    final = CompositeVideoClip([background, band, *captions, *hook_clips], size=(TARGET_W, TARGET_H)).set_audio(full_audio)
    # bitrate esplicito e alto: senza, moviepy/ffmpeg usa un default basso che
    # comprime pesantemente i bordi netti del testo (causa reale dello sfocato).
    final.write_videofile(
        output_path, fps=30, codec="libx264", audio_codec="aac",
        bitrate="8000k", preset="medium", logger=None,
        # moov atom in testa al file invece che in fondo - senza questo il
        # player deve scaricare l'intero file prima di poter leggere i
        # metadati, causando il classico "primo tap non parte, secondo si"
        # (segnalato dall'utente 2026-08-02, moviepy non lo aggiunge di default).
        ffmpeg_params=["-movflags", "+faststart"],
    )
    _normalize_loudness(output_path)
    return output_path
