"""
Вузол 9: Генерація voice-over через edge-tts (безкоштовний TTS від Microsoft).
Склеює hook + body + cta у єдиний текст → генерує mp3 → повертає шлях + тривалість.
"""
import os
import asyncio
import uuid
import edge_tts

from app.state import ReelsState

# Маппінг мова → голос edge-tts
VOICE_MAP = {
    "uk": "uk-UA-PolinaNeural",     # українська жіноча
    "en": "en-US-JennyNeural",      # англійська жіноча
    "ru": "ru-RU-SvetlanaNeural",   # російська жіноча
}

MEDIA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "media", "voiceovers",
)


async def _generate_tts(text: str, voice: str, output_path: str) -> None:
    """Генерує аудіо файл через edge-tts."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def _get_audio_duration(path: str) -> float:
    """Визначає тривалість аудіо через mutagen або fallback."""
    try:
        from mutagen.mp3 import MP3
        audio = MP3(path)
        return audio.info.length
    except Exception:
        # Fallback — оцінка за розміром файлу (≈16kbps для edge-tts)
        size = os.path.getsize(path)
        return size / 16000 * 8


def voiceover_generate(state: ReelsState) -> dict:
    """
    Вузол 9: Генерує voice-over аудіо з фінального скрипта.
    Використовує: edge-tts (безкоштовний, Microsoft Azure voices).
    """
    script = state.get("script", {})
    if not script:
        return {"errors": ["voiceover_generate: no script"]}

    # Збираємо повний текст для озвучки
    parts = [
        script.get("hook", ""),
        script.get("body", ""),
        script.get("cta", ""),
    ]
    full_text = " ".join(p for p in parts if p)

    if not full_text.strip():
        return {"errors": ["voiceover_generate: empty script text"]}

    language = state.get("language", "uk")
    voice = VOICE_MAP.get(language, VOICE_MAP["uk"])

    os.makedirs(MEDIA_DIR, exist_ok=True)
    filename = f"vo_{state.get('project_id', uuid.uuid4().hex[:8])}_{uuid.uuid4().hex[:6]}.mp3"
    output_path = os.path.join(MEDIA_DIR, filename)

    try:
        asyncio.run(_generate_tts(full_text, voice, output_path))
        duration = _get_audio_duration(output_path)

        return {
            "voice_track": output_path,
            "voice_duration_sec": round(duration, 2),
        }
    except Exception as e:
        return {"errors": [f"voiceover_generate error: {str(e)}"]}
