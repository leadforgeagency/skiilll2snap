"""
ElevenLabs voice layer — OPTIONAL. Snap2Skill's core is open-weight Gemma;
this module only adds voice in/out. Every function fails soft: if there is
no ELEVENLABS_API_KEY or the API errors, the app continues in text mode.

Creator plan notes (user's plan): includes Professional Voice Cloning and a
large monthly credit pool. Professional cloning is NOT instant, so the app
exposes Instant Voice Cloning for live use and supports playing back a
pre-created Professional clone by passing its voice_id.
"""
from __future__ import annotations

import io
import os

DEFAULT_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # "George" library voice
FLASH_MODEL = "eleven_flash_v2_5"          # fast, ~half the credits — narration default
MULTILINGUAL_MODEL = "eleven_multilingual_v2"  # use when narrating non-English text


def available() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY"))


def _client():
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        return None
    try:
        from elevenlabs.client import ElevenLabs
    except ImportError:
        return None
    return ElevenLabs(api_key=key)


def transcribe(audio_bytes: bytes) -> dict:
    """ElevenLabs Scribe v2 speech-to-text. Returns {text, language, _mode}."""
    client = _client()
    if client is None or not audio_bytes:
        return {"text": "", "language": None, "_mode": "voice-off"}
    try:
        result = client.speech_to_text.convert(
            file=io.BytesIO(audio_bytes), model_id="scribe_v2")
        return {"text": (getattr(result, "text", "") or "").strip(),
                "language": getattr(result, "language_code", None), "_mode": "elevenlabs-scribe"}
    except Exception as e:
        return {"text": "", "language": None, "_mode": f"scribe-failed: {e}"}


def speak(text: str, voice_id: str | None = None, multilingual: bool = False) -> bytes | None:
    """Text-to-speech -> MP3 bytes, or None if voice is unavailable. Never raises."""
    client = _client()
    text = (text or "").strip()
    if client is None or not text:
        return None
    try:
        audio = client.text_to_speech.convert(
            text=text[:2400],  # keep one skill narration safely inside credit/length limits
            voice_id=(voice_id or DEFAULT_VOICE_ID),
            model_id=MULTILINGUAL_MODEL if multilingual else FLASH_MODEL,
            output_format="mp3_44100_128",
        )
        return b"".join(chunk for chunk in audio if chunk)
    except Exception:
        return None


def narration_script(extraction: dict) -> str:
    """Plain spoken script for a skill: title, purpose, numbered steps, key warnings."""
    title = extraction.get("title", "this skill")
    steps = extraction.get("steps") or []
    parts = [f"{title}.", (extraction.get("description") or "")]
    parts += [f"Step {i}: {s}" for i, s in enumerate(steps, 1)]
    cons = extraction.get("constraints") or []
    if cons:
        parts.append("Important warnings: " + " ".join(cons))
    return " ".join(p.strip() for p in parts if p and p.strip())


def clone_instant_voice(name: str, sample_files: list[bytes]) -> dict:
    """
    Instant Voice Cloning via the ElevenLabs REST API (POST /v1/voices/add).
    For the demo's hero feature, prefer a Professional clone created BEFORE
    the demo (Creator plan) and pass its voice_id to speak(); instant clones
    are the live fallback. Only clone a voice with its owner's consent.
    """
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key or not sample_files:
        return {"voice_id": None, "_mode": "voice-off"}
    try:
        import requests
        files = [("files", (f"sample{i}.mp3", b, "audio/mpeg")) for i, b in enumerate(sample_files)]
        r = requests.post(
            "https://api.elevenlabs.io/v1/voices/add",
            headers={"xi-api-key": key},
            data={"name": name or "Snap2Skill Expert", "description": "Cloned with consent for Snap2Skill narration"},
            files=files, timeout=120,
        )
        if r.ok:
            return {"voice_id": r.json().get("voice_id"), "_mode": "elevenlabs-ivc"}
        return {"voice_id": None, "_mode": f"clone-failed: HTTP {r.status_code} {r.text[:200]}"}
    except Exception as e:
        return {"voice_id": None, "_mode": f"clone-failed: {e}"}
