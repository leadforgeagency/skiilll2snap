"""
HTTP service layer for the Vercel web deployment.

This module is intentionally independent of Streamlit and Flask routing.
It converts JSON payloads from ``public/app.js`` into calls to the same
business modules used by the local Streamlit edition:

* ``gemma_client``  -- open-weight Gemma extraction and translation
* ``voice``         -- optional ElevenLabs Scribe / TTS / voice cloning
* ``skill_builder`` -- deterministic SKILL.md builder, validator and zip packager

Vercel Functions are stateless and have a 4.5 MB request/response ceiling, so
files cross this boundary as base64 JSON. The browser downscales images before
upload; this module still validates every decoded payload server-side.
"""
from __future__ import annotations

import base64
import binascii
import os
import re
from typing import Any

import voice as voice_layer
from gemma_client import extract_skill, translate_text
from samples import SAMPLE_EXTRACTIONS
from skill_builder import (build_skill_md, make_skill_zip, repair_skill_md,
                           slugify, validate_skill_md)

MAX_IMAGE_BYTES = 3_500_000
MAX_AUDIO_BYTES = 3_500_000
MAX_TOTAL_IMAGE_BYTES = 4_000_000
MAX_ZIP_BASE64_CHARS = 4_400_000

STRING_FIELDS = ("skill_name", "title", "description", "evidence")
LIST_FIELDS = ("when_to_use", "prerequisites", "inputs", "steps", "tools",
               "constraints", "unclear_items")


class PayloadError(ValueError):
    """A client-correctable request problem (returned as HTTP 400)."""


def _clean_string(value: Any, limit: int = 20_000) -> str:
    return str(value or "").strip()[:limit]


def _clean_list(value: Any, limit: int = 100) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.splitlines()
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    else:
        raw = [value]
    out: list[str] = []
    for item in raw[:limit]:
        text = str(item or "").strip(" \t-•")
        if text:
            out.append(text[:4_000])
    return out


def clean_extraction(value: Any) -> dict[str, Any]:
    """Keep only the documented extraction schema and make it JSON-safe."""
    if not isinstance(value, dict):
        raise PayloadError("A skill extraction object is required.")

    clean: dict[str, Any] = {}
    for field in STRING_FIELDS:
        clean[field] = _clean_string(value.get(field), 5_000)
    for field in LIST_FIELDS:
        clean[field] = _clean_list(value.get(field))

    examples: list[dict[str, str]] = []
    raw_examples = value.get("examples") or []
    if isinstance(raw_examples, list):
        for item in raw_examples[:5]:
            if isinstance(item, dict):
                examples.append({
                    "input": _clean_string(item.get("input"), 2_000),
                    "output": _clean_string(item.get("output"), 2_000),
                })
    clean["examples"] = examples

    if not clean["title"] and clean["skill_name"]:
        clean["title"] = clean["skill_name"].replace("-", " ").title()
    if not clean["skill_name"] and clean["title"]:
        clean["skill_name"] = slugify(clean["title"])
    clean["skill_name"] = slugify(clean["skill_name"] or "my-skill")

    for field in ("_mode", "_model", "_note"):
        if value.get(field):
            clean[field] = _clean_string(value.get(field), 1_000)
    return clean


def validation_payload(markdown: str, folder_name: str | None = None) -> dict[str, Any]:
    result = validate_skill_md(markdown, folder_name=folder_name)
    return {
        "passed": result["passed"],
        "score": result["score"],
        "total": result["total"],
        "checks": [
            {"name": name, "passed": passed, "detail": detail}
            for name, passed, detail in result["checks"]
        ],
    }


def bootstrap_payload() -> dict[str, Any]:
    gemma_configured = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    return {
        "service": "Snap2Skill",
        "runtime": "Vercel Python Function" if os.getenv("VERCEL") else "local Flask",
        "status": "ready",
        "gemma": {
            "configured": gemma_configured,
            "model": os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it"),
            "mode": "live" if gemma_configured else "demo",
        },
        "elevenlabs": {
            "configured": voice_layer.available(),
            "features": ["Scribe transcription", "Narration", "Instant voice cloning"],
        },
        "limits": {
            "images": 5,
            "function_payload_mb": 4.5,
            "image_strategy": "Browser downscales each snap before upload; the API validates decoded size again.",
        },
        "samples": SAMPLE_EXTRACTIONS,
    }


def decode_upload(item: Any, *, kind: str) -> tuple[bytes, str, str]:
    """Decode one ``{name, mime_type, data_base64}`` object with hard limits."""
    if not isinstance(item, dict):
        raise PayloadError(f"Each {kind} upload must be an object.")
    encoded = item.get("data_base64") or item.get("data") or ""
    if not isinstance(encoded, str) or not encoded:
        raise PayloadError(f"A {kind} upload is missing its base64 data.")
    if encoded.startswith("data:"):
        encoded = encoded.split(",", 1)[-1]
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PayloadError(f"A {kind} upload is not valid base64.") from exc

    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_AUDIO_BYTES
    if len(decoded) > limit:
        raise PayloadError(f"Each {kind} must be 3.5 MB or smaller on Vercel.")
    name = _clean_string(item.get("name"), 200) or f"upload-{kind}"
    mime_type = _clean_string(item.get("mime_type"), 100).lower()
    return decoded, mime_type, name


def extract_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise PayloadError("A JSON object is required.")

    sample_name = _clean_string(payload.get("sample_name"), 300)
    text = _clean_string(payload.get("text"), 30_000)
    notes = _clean_string(payload.get("notes"), 10_000)
    image_items = payload.get("images") or []
    if not isinstance(image_items, list):
        raise PayloadError("Images must be a list.")
    if len(image_items) > 5:
        raise PayloadError("Snap2Skill accepts at most five snaps at once.")

    has_custom_input = bool(text or notes or image_items or payload.get("audio"))
    if sample_name and not has_custom_input:
        if sample_name not in SAMPLE_EXTRACTIONS:
            raise PayloadError("That sample is not available.")
        extraction = dict(SAMPLE_EXTRACTIONS[sample_name])
        extraction["_mode"] = "sample"
        extraction["_model"] = "Built-in labelled sample (no model call)"
        return {
            "extraction": clean_extraction(extraction),
            "transcript": "",
            "transcript_language": None,
            "transcript_mode": "not-used",
        }

    images: list[tuple[bytes, str]] = []
    total_image_bytes = 0
    for item in image_items:
        data, mime_type, _name = decode_upload(item, kind="image")
        if mime_type and not mime_type.startswith("image/"):
            raise PayloadError("Snap uploads must be image files.")
        total_image_bytes += len(data)
        if total_image_bytes > MAX_TOTAL_IMAGE_BYTES:
            raise PayloadError("The five snaps together must stay below 4 MB on Vercel.")
        images.append((data, mime_type or "image/png"))

    transcript = ""
    transcript_language = None
    transcript_mode = "not-used"
    if payload.get("audio"):
        audio_bytes, _mime, _name = decode_upload(payload["audio"], kind="audio")
        spoken = voice_layer.transcribe(audio_bytes)
        transcript = spoken.get("text", "")
        transcript_language = spoken.get("language")
        transcript_mode = spoken.get("_mode", "voice-off")
        if transcript:
            notes = f"{notes}\nExpert voice transcript: {transcript}".strip()
        elif transcript_mode == "voice-off":
            notes = f"{notes}\n(A voice note was supplied, but ElevenLabs is not configured.)".strip()

    extraction = extract_skill(text=text, notes=notes, image_data=images)
    return {
        "extraction": clean_extraction(extraction),
        "transcript": transcript,
        "transcript_language": transcript_language,
        "transcript_mode": transcript_mode,
    }


def build_payload(payload: dict[str, Any]) -> dict[str, Any]:
    extraction = clean_extraction(payload.get("extraction"))
    audio_bytes = None
    if payload.get("audio_base64"):
        audio_bytes, _mime, _name = decode_upload(
            {"data_base64": payload["audio_base64"], "name": "guide.mp3"},
            kind="audio",
        )
    transcript = _clean_string(payload.get("transcript"), 30_000)
    narration_script = _clean_string(payload.get("narration_script"), 10_000)

    folder, zip_bytes, markdown = make_skill_zip(
        extraction,
        audio_bytes=audio_bytes,
        transcript=transcript,
        narration_script=narration_script,
    )
    zip_base64 = base64.b64encode(zip_bytes).decode("ascii")
    zip_included = len(zip_base64) <= MAX_ZIP_BASE64_CHARS
    return {
        "folder": folder,
        "skill_name": folder,
        "skill_md": markdown,
        "validation": validation_payload(markdown, folder_name=folder),
        "zip_base64": zip_base64 if zip_included else "",
        "zip_size_bytes": len(zip_bytes),
        "zip_included": zip_included,
        "zip_warning": "" if zip_included else (
            "The completed zip is too large for one Vercel response. "
            "Download SKILL.md or shorten the narration audio."
        ),
    }


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    markdown = _clean_string(payload.get("markdown"), 100_000)
    if not markdown:
        raise PayloadError("Paste a SKILL.md first.")
    folder = _clean_string(payload.get("folder_name"), 200)
    return {"validation": validation_payload(markdown, folder_name=slugify(folder) if folder else None)}


def repair_payload(payload: dict[str, Any]) -> dict[str, Any]:
    markdown = _clean_string(payload.get("markdown"), 100_000)
    if not markdown:
        raise PayloadError("Paste a SKILL.md first.")
    fixed = repair_skill_md(markdown)
    name_match = re.search(r"^name:\s*(\S+)", fixed, flags=re.MULTILINE)
    folder = name_match.group(1) if name_match else None
    return {
        "skill_md": fixed,
        "folder": folder,
        "validation": validation_payload(fixed, folder_name=folder),
    }


def narrate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    extraction = clean_extraction(payload.get("extraction"))
    language = _clean_string(payload.get("language"), 80) or "English"
    voice_id = _clean_string(payload.get("voice_id"), 200) or None
    script = voice_layer.narration_script(extraction)
    if language.lower() != "english":
        script = translate_text(script, language)

    if not voice_layer.available():
        return {
            "script": script,
            "audio_base64": "",
            "audio_mime": "audio/mpeg",
            "mode": "voice-off",
            "warning": "ElevenLabs is not configured in Vercel. The script is ready and the browser device voice can read it.",
        }

    audio = voice_layer.speak(
        script,
        voice_id=voice_id,
        multilingual=language.lower() != "english",
    )
    if not audio:
        return {
            "script": script,
            "audio_base64": "",
            "audio_mime": "audio/mpeg",
            "mode": "elevenlabs-failed",
            "warning": "ElevenLabs did not return audio. Check its Vercel key, voice ID and credits; the text skill is unaffected.",
        }
    return {
        "script": script,
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "audio_mime": "audio/mpeg",
        "mode": "elevenlabs",
        "warning": "",
    }


def speak_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = _clean_string(payload.get("text"), 1_500)
    if not text:
        raise PayloadError("There is no step text to speak.")
    if not voice_layer.available():
        return {
            "audio_base64": "",
            "audio_mime": "audio/mpeg",
            "mode": "voice-off",
            "warning": "ElevenLabs is not configured; use the browser device voice instead.",
        }
    audio = voice_layer.speak(text, voice_id=_clean_string(payload.get("voice_id"), 200) or None)
    return {
        "audio_base64": base64.b64encode(audio).decode("ascii") if audio else "",
        "audio_mime": "audio/mpeg",
        "mode": "elevenlabs" if audio else "elevenlabs-failed",
        "warning": "" if audio else "ElevenLabs did not return audio for this step.",
    }


def clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("consent") is not True:
        raise PayloadError("Voice cloning requires explicit consent from the voice owner.")
    name = _clean_string(payload.get("name"), 200)
    if not name:
        raise PayloadError("Give the expert voice a name.")
    items = payload.get("samples") or []
    if not isinstance(items, list) or not items:
        raise PayloadError("Upload at least one voice sample.")
    if len(items) > 5:
        raise PayloadError("Use at most five voice samples.")

    samples: list[bytes] = []
    total = 0
    for item in items:
        data, _mime, _name = decode_upload(item, kind="audio")
        total += len(data)
        if total > MAX_TOTAL_IMAGE_BYTES:
            raise PayloadError("Voice samples together must stay below 4 MB on Vercel.")
        samples.append(data)

    result = voice_layer.clone_instant_voice(name, samples)
    return {
        "voice_id": result.get("voice_id"),
        "mode": result.get("_mode", "unknown"),
        "warning": "" if result.get("voice_id") else "Cloning did not complete. Check the ElevenLabs key, plan and sample quality.",
    }
