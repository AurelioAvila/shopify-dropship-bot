"""
Genera l'audio (voce) a partire dal copione, usando edge-tts (gratuito,
nessuna API key). Stessa logica del bot YouTube Shorts, adattata per
i video promozionali dello store.
"""
import asyncio
import time

import edge_tts

DEFAULT_VOICE = "it-IT-DiegoNeural"
DEFAULT_RATE = "+0%"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


async def _generate_with_timing(text: str, output_path: str, voice: str, rate: str) -> list:
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    word_timings = []
    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"] / 1e7,
                    "duration": chunk["duration"] / 1e7,
                })
    return word_timings


def generate_audio_with_timing(text: str, output_path: str, voice: str = DEFAULT_VOICE,
                                rate: str = DEFAULT_RATE) -> list:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return asyncio.run(_generate_with_timing(text, output_path, voice, rate))
        except Exception as e:
            last_error = e
            print(f"[tts] tentativo {attempt}/{MAX_RETRIES} fallito: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)
    raise last_error
