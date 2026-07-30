"""
Monta un video promozionale verticale (1080x1920) a partire da:
- una lista di immagini prodotto (effetto Ken Burns: leggero zoom/pan)
- un copione, letto con voce IA (edge-tts) e sottotitolato in automatico
Stessa impostazione visiva (font, stroke, banda sottotitoli) del bot Shorts.
"""
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

import requests
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
)

from src.tts import generate_audio_with_timing

TARGET_W, TARGET_H = 1080, 1920
CAPTION_CHUNK_SIZE = 3
CAPTION_FONTSIZE = 76
CAPTION_Y = int(TARGET_H * 0.62)


def download_images(urls: list[str], tmp_dir: str) -> list[str]:
    os.makedirs(tmp_dir, exist_ok=True)
    paths = []
    for i, url in enumerate(urls):
        path = os.path.join(tmp_dir, f"img_{i}.jpg")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
        paths.append(path)
    return paths


def _ken_burns_clip(image_path: str, duration: float, zoom_in: bool = True) -> ImageClip:
    clip = ImageClip(image_path)
    # riempi il frame verticale (cover-crop) prima di applicare lo zoom
    if clip.w / clip.h > TARGET_W / TARGET_H:
        clip = clip.resize(height=TARGET_H)
    else:
        clip = clip.resize(width=TARGET_W)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=TARGET_W, height=TARGET_H)

    start_scale, end_scale = (1.0, 1.15) if zoom_in else (1.15, 1.0)

    def scale_at(t):
        progress = t / duration
        return start_scale + (end_scale - start_scale) * progress

    zoomed = clip.resize(lambda t: scale_at(t)).set_position(("center", "center"))
    return CompositeVideoClip([zoomed], size=(TARGET_W, TARGET_H)).set_duration(duration)


def _make_caption_clip(text: str, start: float, duration: float):
    return (
        TextClip(
            text, fontsize=CAPTION_FONTSIZE, color="white", stroke_color="black",
            stroke_width=4, method="caption", size=(TARGET_W - 100, None),
            font="DejaVu-Sans-Bold",
        )
        .set_start(start)
        .set_duration(max(duration, 0.1))
        .set_position(("center", CAPTION_Y))
    )


def _caption_clips_timed(word_timings: list):
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
        clips.append(_make_caption_clip(text, start, end - start))
    return clips


# Durata massima per singola immagine prima del prossimo taglio - stile
# retention-optimized Shorts (tagli rapidi), non slideshow lento.
MAX_SEGMENT_SECONDS = 2.5


def build_promo_video(script_text: str, image_urls: list[str], output_path: str, tmp_dir: str) -> str:
    audio_path = output_path.replace(".mp4", ".mp3")
    word_timings = generate_audio_with_timing(script_text, audio_path)
    audio = AudioFileClip(audio_path)
    duration = audio.duration

    local_images = download_images(image_urls, tmp_dir)
    # Numero di segmenti = quanti tagli servono per stare sotto MAX_SEGMENT_SECONDS,
    # ma mai piu' immagini distinte di quelle disponibili moltiplicate per 2
    # (oltre le quali ricicleremmo troppo la stessa foto, diventa ripetitivo).
    import math
    target_segments = max(len(local_images), math.ceil(duration / MAX_SEGMENT_SECONDS))
    target_segments = min(target_segments, len(local_images) * 2)
    per_image = duration / target_segments

    image_clips = []
    for i in range(target_segments):
        path = local_images[i % len(local_images)]
        # alterna zoom-in/zoom-out ogni volta, cosi' anche quando la stessa
        # immagine si ripete il movimento e' diverso e non sembra uno stallo
        image_clips.append(_ken_burns_clip(path, per_image, zoom_in=(i % 2 == 0)))
    background = concatenate_videoclips(image_clips).set_duration(duration)

    captions = _caption_clips_timed(word_timings)
    final = CompositeVideoClip([background, *captions], size=(TARGET_W, TARGET_H)).set_audio(audio)
    # bitrate esplicito e alto: senza, moviepy/ffmpeg usa un default basso che
    # comprime pesantemente i bordi netti del testo (causa reale dello sfocato).
    final.write_videofile(
        output_path, fps=30, codec="libx264", audio_codec="aac",
        bitrate="8000k", preset="medium", logger=None,
    )
    return output_path
